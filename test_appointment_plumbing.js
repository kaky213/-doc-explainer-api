// Test appointment field plumbing
const mockAppointmentDocument = {
    document_analysis_enabled: true,
    document_type: "medical_bill",
    document_type_confidence: "high",
    document_summary: "This appears to be a medical appointment reminder. It shows appointment details including date, time, and location.",
    key_details: [
        {"label": "Appointment date", "value": "2026-05-15", "confidence": "high"},
        {"label": "Appointment time", "value": "10:00 AM", "confidence": "high"},
        {"label": "Location", "value": "Westside Clinic - Room 205", "confidence": "medium"},
        {"label": "Provider", "value": "Dr. Sarah Johnson", "confidence": "high"},
        {"label": "Patient name", "value": "Jane R. Doe", "confidence": "high"}
    ],
    amount_due: null,
    due_date: null,
    sender_name: "Westside Medical Group",
    reference_number: "REM-2026-5678",
    suggested_actions: [
        "Confirm the appointment date and time.",
        "Arrive 15 minutes early for check-in.",
        "Bring your insurance card and ID."
    ],
    confidence_notes: "All appointment details appear clear.",
    appointment_date: "2026-05-15",
    appointment_time: "10:00 AM",
    appointment_location: "Westside Clinic - Room 205",
    provider_name: "Dr. Sarah Johnson",
    patient_name: "Jane R. Doe",
    bill_period_start: null,
    bill_period_end: null,
    statement_date: null,
    balance_previous: null,
    payments_since_last: null,
    response_deadline: null,
    case_number: null,
    form_identifier: null
};

console.log("=== Testing Appointment Field Plumbing ===");
console.log("Document has appointment fields:");
console.log("- appointment_date:", mockAppointmentDocument.appointment_date);
console.log("- appointment_time:", mockAppointmentDocument.appointment_time);
console.log("- appointment_location:", mockAppointmentDocument.appointment_location);
console.log("- provider_name:", mockAppointmentDocument.provider_name);
console.log("- patient_name:", mockAppointmentDocument.patient_name);

// Simulate the frontend logic
function getFieldConfidence(fieldValue, fieldName) {
    if (!fieldValue) return 'low';
    if (fieldValue.toLowerCase().includes('not found') || 
        fieldValue.toLowerCase().includes('unclear') ||
        fieldValue.toLowerCase().includes('unknown')) {
        return 'low';
    }
    return 'medium';
}

const allKeyDetails = [];

// Add AI-generated key_details if present
if (mockAppointmentDocument.key_details && mockAppointmentDocument.key_details.length > 0) {
    mockAppointmentDocument.key_details.forEach(detail => {
        if (detail.label && detail.value && detail.confidence) {
            allKeyDetails.push(detail);
        }
    });
}

// Add appointment-specific fields if present
if (mockAppointmentDocument.appointment_date || mockAppointmentDocument.appointment_time || mockAppointmentDocument.appointment_location || 
    mockAppointmentDocument.provider_name || mockAppointmentDocument.patient_name) {
    
    if (mockAppointmentDocument.appointment_date) {
        allKeyDetails.push({
            label: 'Appointment date',
            value: mockAppointmentDocument.appointment_date,
            confidence: getFieldConfidence(mockAppointmentDocument.appointment_date, 'appointment_date')
        });
    }
    
    if (mockAppointmentDocument.appointment_time) {
        allKeyDetails.push({
            label: 'Appointment time',
            value: mockAppointmentDocument.appointment_time,
            confidence: getFieldConfidence(mockAppointmentDocument.appointment_time, 'appointment_time')
        });
    }
    
    if (mockAppointmentDocument.appointment_location) {
        allKeyDetails.push({
            label: 'Location',
            value: mockAppointmentDocument.appointment_location,
            confidence: getFieldConfidence(mockAppointmentDocument.appointment_location, 'appointment_location')
        });
    }
    
    if (mockAppointmentDocument.provider_name) {
        allKeyDetails.push({
            label: 'Provider',
            value: mockAppointmentDocument.provider_name,
            confidence: getFieldConfidence(mockAppointmentDocument.provider_name, 'provider_name')
        });
    }
    
    if (mockAppointmentDocument.patient_name) {
        allKeyDetails.push({
            label: 'Patient name',
            value: mockAppointmentDocument.patient_name,
            confidence: getFieldConfidence(mockAppointmentDocument.patient_name, 'patient_name')
        });
    }
}

console.log("\n=== Frontend Processing Results ===");
console.log("Total key details after processing:", allKeyDetails.length);
console.log("Key details to be rendered:");
allKeyDetails.forEach((detail, index) => {
    console.log(`${index + 1}. ${detail.label}: ${detail.value} (${detail.confidence} confidence)`);
});

// Check for duplicates
const detailLabels = allKeyDetails.map(d => d.label);
const uniqueLabels = [...new Set(detailLabels)];
console.log("\n=== Duplicate Check ===");
console.log("Total labels:", detailLabels.length);
console.log("Unique labels:", uniqueLabels.length);
if (detailLabels.length !== uniqueLabels.length) {
    console.log("⚠️ DUPLICATES FOUND!");
    const duplicates = detailLabels.filter((item, index) => detailLabels.indexOf(item) !== index);
    console.log("Duplicate labels:", duplicates);
} else {
    console.log("✅ No duplicates found");
}