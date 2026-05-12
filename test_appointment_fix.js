// Test the appointment field fix
const mockAppointmentDocument = {
    document_analysis_enabled: true,
    document_type: "medical_bill",
    document_type_confidence: "high",
    document_summary: "This appears to be a medical appointment reminder.",
    key_details: [
        {"label": "Appointment date", "value": "2026-05-15", "confidence": "high"},
        {"label": "Appointment time", "value": "10:00 AM", "confidence": "high"},
        {"label": "Location", "value": "Westside Clinic - Room 205", "confidence": "medium"},
        {"label": "Provider", "value": "Dr. Sarah Johnson", "confidence": "high"},
        {"label": "Patient name", "value": "Jane R. Doe", "confidence": "high"}
    ],
    appointment_date: "2026-05-15",
    appointment_time: "10:00 AM",
    appointment_location: "Westside Clinic - Room 205",
    provider_name: "Dr. Sarah Johnson",
    patient_name: "Jane R. Doe"
};

console.log("=== Testing Fixed Appointment Logic ===");

const docType = mockAppointmentDocument.document_type;
const allKeyDetails = [];

// Add AI-generated key_details if present
if (mockAppointmentDocument.key_details && mockAppointmentDocument.key_details.length > 0) {
    mockAppointmentDocument.key_details.forEach(detail => {
        if (detail.label && detail.value && detail.confidence) {
            allKeyDetails.push(detail);
        }
    });
}

console.log("After adding AI key_details:", allKeyDetails.length, "items");

// Check which fields are already in key_details
const existingLabels = allKeyDetails.map(detail => detail.label.toLowerCase());

// Helper to check if a field is already in key_details
const isFieldAlreadyPresent = (fieldLabel) => {
    return existingLabels.some(label => label.includes(fieldLabel.toLowerCase()));
};

// For appointment documents, ensure key fields are shown even if AI missed them
const isAppointmentDoc = docType.includes('appointment') || docType === 'medical_bill';

console.log("Is appointment doc?", isAppointmentDoc);
console.log("Existing labels:", existingLabels);

if (isAppointmentDoc) {
    // Determine confidence for appointment fields
    const getFieldConfidence = (fieldValue, fieldName) => {
        if (!fieldValue) return 'low';
        // Check if field looks like a placeholder or default
        if (fieldValue.toLowerCase().includes('not found') || 
            fieldValue.toLowerCase().includes('unclear') ||
            fieldValue.toLowerCase().includes('unknown')) {
            return 'low';
        }
        return 'medium'; // Default confidence for extracted fields
    };
    
    // Appointment date - add if missing
    if (!isFieldAlreadyPresent('appointment date')) {
        if (mockAppointmentDocument.appointment_date) {
            allKeyDetails.push({
                label: 'Appointment date',
                value: mockAppointmentDocument.appointment_date,
                confidence: getFieldConfidence(mockAppointmentDocument.appointment_date, 'appointment_date')
            });
            console.log("Added appointment date (was missing)");
        } else {
            allKeyDetails.push({
                label: 'Appointment date',
                value: 'Not clearly found in this photo.',
                confidence: 'low'
            });
            console.log("Added missing appointment date fallback");
        }
    } else {
        console.log("Appointment date already present, skipping");
    }
    
    // Appointment time - add if missing
    if (!isFieldAlreadyPresent('appointment time')) {
        if (mockAppointmentDocument.appointment_time) {
            allKeyDetails.push({
                label: 'Appointment time',
                value: mockAppointmentDocument.appointment_time,
                confidence: getFieldConfidence(mockAppointmentDocument.appointment_time, 'appointment_time')
            });
            console.log("Added appointment time (was missing)");
        } else {
            allKeyDetails.push({
                label: 'Appointment time',
                value: 'Not clearly found in this photo.',
                confidence: 'low'
            });
            console.log("Added missing appointment time fallback");
        }
    } else {
        console.log("Appointment time already present, skipping");
    }
    
    // Location - add if missing (check for 'location' or 'appointment location')
    const hasLocationField = isFieldAlreadyPresent('location') || isFieldAlreadyPresent('appointment location');
    if (!hasLocationField && mockAppointmentDocument.appointment_location) {
        allKeyDetails.push({
            label: 'Location',
            value: mockAppointmentDocument.appointment_location,
            confidence: getFieldConfidence(mockAppointmentDocument.appointment_location, 'appointment_location')
        });
        console.log("Added location (was missing)");
    } else if (!hasLocationField) {
        console.log("Location not in key_details, but no appointment_location field either");
    } else {
        console.log("Location already present, skipping");
    }
    
    // Provider - add if missing
    if (!isFieldAlreadyPresent('provider') && mockAppointmentDocument.provider_name) {
        allKeyDetails.push({
            label: 'Provider',
            value: mockAppointmentDocument.provider_name,
            confidence: getFieldConfidence(mockAppointmentDocument.provider_name, 'provider_name')
        });
        console.log("Added provider (was missing)");
    } else if (!isFieldAlreadyPresent('provider')) {
        console.log("Provider not in key_details, but no provider_name field either");
    } else {
        console.log("Provider already present, skipping");
    }
    
    // Patient name - add if missing
    if (!isFieldAlreadyPresent('patient name') && mockAppointmentDocument.patient_name) {
        allKeyDetails.push({
            label: 'Patient name',
            value: mockAppointmentDocument.patient_name,
            confidence: getFieldConfidence(mockAppointmentDocument.patient_name, 'patient_name')
        });
        console.log("Added patient name (was missing)");
    } else if (!isFieldAlreadyPresent('patient name')) {
        console.log("Patient name not in key_details, but no patient_name field either");
    } else {
        console.log("Patient name already present, skipping");
    }
}

console.log("\n=== Final Results ===");
console.log("Total key details:", allKeyDetails.length);
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
    console.log("❌ DUPLICATES STILL FOUND!");
    const duplicates = detailLabels.filter((item, index) => detailLabels.indexOf(item) !== index);
    console.log("Duplicate labels:", duplicates);
} else {
    console.log("✅ No duplicates found - FIXED!");
}

// Test case 2: AI misses some fields
console.log("\n\n=== Test Case 2: AI Misses Some Fields ===");
const mockPartialDocument = {
    document_analysis_enabled: true,
    document_type: "medical_bill",
    document_type_confidence: "high",
    key_details: [
        {"label": "Appointment date", "value": "2026-05-15", "confidence": "high"},
        // AI missed appointment_time, location, provider_name, patient_name
    ],
    appointment_date: "2026-05-15",
    appointment_time: "10:00 AM", // But direct field has it
    appointment_location: "Westside Clinic",
    provider_name: "Dr. Smith",
    patient_name: "John Doe"
};

console.log("Testing partial AI response with direct fields...");
// Simulate the logic... (would need full implementation)
console.log("Expected: Should add missing fields from direct fields");
console.log("Appointment time, location, provider, patient name should be added");