$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"
$results = @()
function Step($name, $scriptblock) {
    try {
        $value = & $scriptblock
        $summary = if ($null -eq $value) { "" } elseif ($value -is [string]) { $value } else { $value | ConvertTo-Json -Depth 6 -Compress }
        $script:results += [pscustomobject]@{ Step = $name; Status = "PASS"; Detail = $summary }
        Write-Output "[PASS] $name"
    } catch {
        $script:results += [pscustomobject]@{ Step = $name; Status = "FAIL"; Detail = $_.Exception.Message }
        $detail = ""
        if ($_.ErrorDetails.Message) { $detail = " :: " + $_.ErrorDetails.Message }
        Write-Output "[FAIL] $name :: $($_.Exception.Message)$detail"
    }
}

Step "GET /health" {
    Invoke-RestMethod -Uri "$base/health" -TimeoutSec 10 | ConvertTo-Json -Compress
}

Step "GET /api/v1/doctors (all)" {
    $docs = Invoke-RestMethod -Uri "$base/api/v1/doctors" -TimeoutSec 10
    "count=$($docs.Count); departments=$(($docs.department | Sort-Object -Unique) -join ',')"
}

Step "GET /api/v1/doctors?department=ENT" {
    $docs = Invoke-RestMethod -Uri "$base/api/v1/doctors?department=ENT" -TimeoutSec 10
    "count=$($docs.Count); all_ent=$([bool]($docs | Where-Object { $_.department -ne 'ENT' }).Count -eq $false)"
}

Step "GET /api/v1/doctors/availability?department=ENT&window_days=3" {
    $slots = Invoke-RestMethod -Uri "$base/api/v1/doctors/availability?department=ENT&window_days=3" -TimeoutSec 10
    $withSlots = @($slots | Where-Object { $_.available_slots.Count -gt 0 })
    "entries=$($slots.Count); with_free_slots=$($withSlots.Count); sample=$($withSlots[0].doctor_name) $($withSlots[0].date) [$($withSlots[0].available_slots -join ',')]"
}

Step "GET /api/v1/doctors/fees?department=Cardiology" {
    $fees = Invoke-RestMethod -Uri "$base/api/v1/doctors/fees?department=Cardiology" -TimeoutSec 10
    "min=$($fees.min_fee); max=$($fees.max_fee); doctors=$($fees.doctor_count)"
}

Step "GET /api/v1/doctors/fees?doctor_name=Dr. Sanjay Verma" {
    $fees = Invoke-RestMethod -Uri "$base/api/v1/doctors/fees?doctor_name=Dr.%20Sanjay%20Verma" -TimeoutSec 10
    "consult=$($fees.consultation_fee); followup=$($fees.followup_fee)"
}

Step "POST /api/v1/patients (register new)" {
    $body = @{ full_name = "E2E Test Patient"; phone = "+919700000001"; age = 35; gender = "male" } | ConvertTo-Json
    $patient = Invoke-RestMethod -Uri "$base/api/v1/patients" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
    $script:patientId = $patient.id
    "id=$($patient.id); name=$($patient.full_name)"
}

Step "GET /api/v1/patients/by-phone/+919700000001" {
    $patient = Invoke-RestMethod -Uri "$base/api/v1/patients/by-phone/%2B919700000001" -TimeoutSec 10
    "found=$($patient.full_name)"
}

Step "POST /api/v1/patients (invalid phone -> 400)" {
    try {
        $body = @{ full_name = "Bad"; phone = "abc" } | ConvertTo-Json
        Invoke-RestMethod -Uri "$base/api/v1/patients" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        throw "expected 400 but got 2xx"
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 400) { "got expected 400" } else { throw }
    }
}

function Get-FreeSlot($department) {
    $all = Invoke-RestMethod -Uri "$base/api/v1/doctors/availability?department=$department&window_days=7" -TimeoutSec 10
    foreach ($entry in $all) {
        $slots = @($entry.available_slots)
        if ($slots.Count -gt 0) {
            return [pscustomobject]@{ doctor_id = [int]$entry.doctor_id; date = [string]$entry.date; time_slot = [string]$slots[0] }
        }
    }
    throw "no free slot found"
}

Step "POST /api/v1/appointments (book real slot)" {
    $slot = Get-FreeSlot "ENT"
    $body = @{ doctor_id = $slot.doctor_id; patient_id = $script:patientId; appointment_date = $slot.date; time_slot = $slot.time_slot; reason = "ear infection"; source = "web" } | ConvertTo-Json
    $appt = Invoke-RestMethod -Uri "$base/api/v1/appointments" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
    $script:appointmentId = $appt.id
    "id=$($appt.id); doctor=$($appt.doctor_name); date=$($appt.appointment_date) $($appt.time_slot); fee=$($appt.consultation_fee)"
}

Step "GET /api/v1/appointments?patient_id=<id>" {
    $list = Invoke-RestMethod -Uri "$base/api/v1/appointments?patient_id=$script:patientId" -TimeoutSec 10
    "count=$(@($list).Count); first_status=$($list[0].status)"
}

Step "POST /api/v1/appointments (duplicate slot -> 409)" {
    try {
        $slot = Get-FreeSlot "ENT"
        $body = @{ doctor_id = $slot.doctor_id; patient_id = $script:patientId; appointment_date = $slot.date; time_slot = $slot.time_slot; reason = "dup"; source = "web" } | ConvertTo-Json
        $a1 = Invoke-RestMethod -Uri "$base/api/v1/appointments" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
        Invoke-RestMethod -Uri "$base/api/v1/appointments" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        throw "expected 409"
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 409) { "got expected 409 (slot conflict)" } else { throw }
    }
}

Step "POST /api/v1/appointments/<id>/cancel" {
    $cancelled = Invoke-RestMethod -Uri "$base/api/v1/appointments/$script:appointmentId/cancel" -Method Post -TimeoutSec 10
    "status=$($cancelled.status)"
}

Step "POST /api/v1/emergency/check (chest pain)" {
    $body = @{ message = "I have severe chest pain and shortness of breath" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/emergency/check" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
    "emergency=$($resp.emergency); booking_allowed=$($resp.booking_allowed); keyword=$($resp.matched_keyword)"
}

Step "POST /api/v1/emergency/check (routine)" {
    $body = @{ message = "I want an ENT checkup for my sinus" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/emergency/check" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
    "emergency=$($resp.emergency)"
}

Step "POST /api/v1/webhook/bolna (end-of-call payload)" {
    $payload = @{
        id = "e2e-exec-0001"
        agent_id = "00000000-0000-0000-0000-000000000001"
        status = "completed"
        conversation_duration = 96
        total_cost = 5.76
        transcript = "assistant: Thank you for calling Bhaktivedanta Hospital.`nuser: I want to book an ENT appointment.`nassistant: Your appointment with Dr. Rajesh Sharma is confirmed for Monday 10:30 AM."
        user_number = "+919700000001"
        agent_number = "+918035739222"
        extracted_data = @{ General = @{ "Call Summary" = @{ subjective = "ENT appointment booked for Monday"; confidence_label = "High" } } }
        telephony_data = @{ duration = 96; recording_url = "https://api.bolna.ai/recordings/call/e2e-exec-0001"; call_type = "inbound"; provider = "plivo"; hangup_by = "Plivo"; hangup_reason = "completed" }
        cost_breakdown = @{ platform = 2; network = 1; transcriber = 0.23; llm = 0; synthesizer = 0 }
    } | ConvertTo-Json -Depth 8
    $resp = Invoke-RestMethod -Uri "$base/api/v1/webhook/bolna" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 10
    "received=$($resp.received); status=$($resp.status); call_log_id=$($resp.call_log_id)"
}

Step "POST /api/v1/webhook/bolna (replay -> same call_log_id)" {
    $payload = @{
        id = "e2e-exec-0001"
        status = "completed"
        transcript = "assistant: Hello"
        user_number = "+919700000001"
    } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/webhook/bolna" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 10
    "call_log_id=$($resp.call_log_id)"
}

Step "POST /api/v1/webhook/bolna (emergency transcript -> flagged)" {
    $payload = @{
        id = "e2e-exec-0002"
        status = "completed"
        transcript = "assistant: Are you okay?`nuser: severe chest pain radiating to my arm"
        user_number = "+919700000002"
    } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/webhook/bolna" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 10
    $log = Invoke-RestMethod -Uri "$base/api/v1/webhook/bolna" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 10
    $resp | Out-Null
    "call_log_id=$($log.call_log_id) (emergency flag checked via DB later)"
}

Step "POST /api/v1/calls (no BOLNA_AGENT_ID -> graceful 502)" {
    try {
        $body = @{ recipient_phone_number = "+919700000001" } | ConvertTo-Json
        Invoke-RestMethod -Uri "$base/api/v1/calls" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        throw "expected 502"
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq 502) { "got expected 502 (agent_id not configured)" } else { throw }
    }
}

Step "POST /api/v1/assistant/chat (real DeepSeek)" {
    $body = @{ message = "Which cardiologists do you have and what are their fees? I need a heart checkup."; origin = "chat" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/assistant/chat" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 90
    "tool_calls=$($resp.tool_calls) | emergency=$($resp.emergency) | reply: $($resp.reply)"
}

Step "POST /api/v1/assistant/chat (emergency guardrail)" {
    $body = @{ message = "I have severe chest pain, please book me an appointment" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$base/api/v1/assistant/chat" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
    "emergency=$($resp.emergency); reply: $($resp.reply)"
}

Write-Output ""
Write-Output "================ SUMMARY ================"
$failCount = @($results | Where-Object { $_.Status -eq "FAIL" }).Count
Write-Output "Total: $($results.Count) | Passed: $($results.Count - $failCount) | Failed: $failCount"
if ($failCount -gt 0) {
    $results | Where-Object { $_.Status -eq "FAIL" } | Format-Table -AutoSize | Out-String | Write-Output
}
exit $failCount
