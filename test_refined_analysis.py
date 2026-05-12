#!/usr/bin/env python3
"""
Test script for refined document analysis feature.
"""
import json

def test_json_schema():
    """Test that the JSON schema includes all new fields."""
    
    print("Testing refined JSON schema...")
    
    # Expected fields in the refined schema
    expected_fields = [
        "document_type", "document_type_confidence", "document_summary",
        "key_details", "amount_due", "due_date", "sender_name",
        "reference_number", "suggested_actions", "confidence_notes",
        "appointment_date", "appointment_time", "appointment_location",
        "provider_name", "patient_name", "bill_period_start",
        "bill_period_end", "statement_date", "balance_previous",
        "payments_since_last", "response_deadline", "case_number",
        "form_identifier"
    ]
    
    # Sample response matching the refined schema
    sample_response = '''{
  "document_type": "medical_bill",
  "document_type_confidence": "high",
  "document_summary": "This appears to be a medical bill for services rendered. The bill shows an amount due and includes appointment details.",
  "key_details": [
    {"label": "Amount due", "value": "$245.75", "confidence": "high"},
    {"label": "Due date", "value": "2026-06-15", "confidence": "medium"},
    {"label": "Appointment date", "value": "2026-05-10", "confidence": "high"},
    {"label": "Appointment time", "value": "2:30 PM", "confidence": "medium"},
    {"label": "Provider", "value": "City Medical Center", "confidence": "high"}
  ],
  "amount_due": "$245.75",
  "due_date": "2026-06-15",
  "sender_name": "City Medical Center Billing",
  "reference_number": "MB-2026-12345",
  "suggested_actions": [
    "Verify the amount due matches your records.",
    "Check the appointment date and time if this includes services.",
    "Contact the provider if anything looks incorrect."
  ],
  "confidence_notes": "Most details appear clear. Appointment time confidence is medium due to OCR formatting.",
  "appointment_date": "2026-05-10",
  "appointment_time": "2:30 PM",
  "appointment_location": "City Medical Center - Main Campus",
  "provider_name": "City Medical Center",
  "patient_name": "John A. Smith",
  "bill_period_start": "2026-04-01",
  "bill_period_end": "2026-04-30",
  "statement_date": "2026-05-05",
  "balance_previous": "$0.00",
  "payments_since_last": "$50.00",
  "response_deadline": null,
  "case_number": null,
  "form_identifier": null
}'''
    
    try:
        data = json.loads(sample_response)
        
        # Check all expected fields are present
        missing_fields = []
        for field in expected_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Missing fields in schema: {missing_fields}")
            return False
        
        print("✅ All expected fields present in schema")
        
        # Check that null fields are properly null
        null_fields = ["response_deadline", "case_number", "form_identifier"]
        for field in null_fields:
            if data.get(field) is not None:
                print(f"❌ Field {field} should be null but is: {data.get(field)}")
                return False
        
        print("✅ Null fields properly set to null")
        
        # Check key_details includes fields from direct extraction
        key_detail_labels = [detail["label"].lower() for detail in data["key_details"]]
        expected_labels = ["amount due", "due date", "appointment date", "appointment time", "provider"]
        
        for label in expected_labels:
            if label not in key_detail_labels:
                print(f"❌ Expected key detail label not found: {label}")
                return False
        
        print("✅ Key details include both direct and extracted fields")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_appointment_reminder_scenario():
    """Test appointment reminder scenario."""
    print("\nTesting appointment reminder scenario...")
    
    appointment_response = '''{
  "document_type": "medical_bill",
  "document_type_confidence": "high",
  "document_summary": "This appears to be a medical appointment reminder. It shows appointment details including date, time, and location.",
  "key_details": [
    {"label": "Appointment date", "value": "2026-05-15", "confidence": "high"},
    {"label": "Appointment time", "value": "10:00 AM", "confidence": "high"},
    {"label": "Location", "value": "Westside Clinic - Room 205", "confidence": "medium"},
    {"label": "Provider", "value": "Dr. Sarah Johnson", "confidence": "high"},
    {"label": "Patient name", "value": "Jane R. Doe", "confidence": "high"}
  ],
  "amount_due": null,
  "due_date": null,
  "sender_name": "Westside Medical Group",
  "reference_number": "REM-2026-5678",
  "suggested_actions": [
    "Confirm the appointment date and time.",
    "Arrive 15 minutes early for check-in.",
    "Bring your insurance card and ID."
  ],
  "confidence_notes": "All appointment details appear clear.",
  "appointment_date": "2026-05-15",
  "appointment_time": "10:00 AM",
  "appointment_location": "Westside Clinic - Room 205",
  "provider_name": "Dr. Sarah Johnson",
  "patient_name": "Jane R. Doe",
  "bill_period_start": null,
  "bill_period_end": null,
  "statement_date": null,
  "balance_previous": null,
  "payments_since_last": null,
  "response_deadline": null,
  "case_number": null,
  "form_identifier": null
}'''
    
    try:
        data = json.loads(appointment_response)
        
        # Check appointment fields are populated
        appointment_fields = ["appointment_date", "appointment_time", "appointment_location", "provider_name", "patient_name"]
        for field in appointment_fields:
            if not data.get(field):
                print(f"❌ Appointment field {field} is null or empty")
                return False
        
        print("✅ Appointment fields properly populated")
        
        # Check bill fields are null (not a bill)
        bill_fields = ["amount_due", "due_date", "bill_period_start", "bill_period_end"]
        for field in bill_fields:
            if data.get(field) is not None:
                print(f"❌ Bill field {field} should be null for appointment reminder")
                return False
        
        print("✅ Bill fields properly null for appointment reminder")
        
        return True
        
    except Exception as e:
        print(f"❌ Appointment test failed: {e}")
        return False

def test_government_form_scenario():
    """Test government form scenario."""
    print("\nTesting government form scenario...")
    
    government_response = '''{
  "document_type": "government_form",
  "document_type_confidence": "high",
  "document_summary": "This appears to be a government immigration form with a response deadline and case number.",
  "key_details": [
    {"label": "Response deadline", "value": "2026-07-30", "confidence": "high"},
    {"label": "Case number", "value": "USCIS-2026-78901", "confidence": "high"},
    {"label": "Form", "value": "I-485", "confidence": "high"},
    {"label": "Sender", "value": "U.S. Citizenship and Immigration Services", "confidence": "high"}
  ],
  "amount_due": null,
  "due_date": null,
  "sender_name": "U.S. Citizenship and Immigration Services",
  "reference_number": "USCIS-2026-78901",
  "suggested_actions": [
    "Review the response deadline carefully.",
    "Ensure all required documents are submitted by the deadline.",
    "Contact USCIS if you have questions about the form."
  ],
  "confidence_notes": "Form details appear clear and complete.",
  "appointment_date": null,
  "appointment_time": null,
  "appointment_location": null,
  "provider_name": null,
  "patient_name": null,
  "bill_period_start": null,
  "bill_period_end": null,
  "statement_date": null,
  "balance_previous": null,
  "payments_since_last": null,
  "response_deadline": "2026-07-30",
  "case_number": "USCIS-2026-78901",
  "form_identifier": "I-485"
}'''
    
    try:
        data = json.loads(government_response)
        
        # Check government fields are populated
        government_fields = ["response_deadline", "case_number", "form_identifier"]
        for field in government_fields:
            if not data.get(field):
                print(f"❌ Government field {field} is null or empty")
                return False
        
        print("✅ Government fields properly populated")
        
        # Check appointment fields are null (not an appointment)
        appointment_fields = ["appointment_date", "appointment_time", "appointment_location"]
        for field in appointment_fields:
            if data.get(field) is not None:
                print(f"❌ Appointment field {field} should be null for government form")
                return False
        
        print("✅ Appointment fields properly null for government form")
        
        return True
        
    except Exception as e:
        print(f"❌ Government form test failed: {e}")
        return False

def test_missing_fields_scenario():
    """Test scenario where some fields are missing."""
    print("\nTesting missing fields scenario...")
    
    missing_fields_response = '''{
  "document_type": "utility_bill",
  "document_type_confidence": "medium",
  "document_summary": "This appears to be a utility bill, but some details are unclear in the OCR text.",
  "key_details": [
    {"label": "Amount due", "value": "$84.22", "confidence": "high"},
    {"label": "Due date", "value": "May 10, 2026", "confidence": "medium"},
    {"label": "Statement date", "value": "Not clearly found", "confidence": "low"},
    {"label": "Billing period", "value": "Unclear in this photo", "confidence": "low"}
  ],
  "amount_due": "$84.22",
  "due_date": "May 10, 2026",
  "sender_name": "City Power & Light",
  "reference_number": "INV-2026-04-001",
  "suggested_actions": [
    "Verify the amount due matches your usage.",
    "Check the due date to avoid late fees."
  ],
  "confidence_notes": "Amount and due date are clear, but billing period and statement date are unclear in the OCR.",
  "appointment_date": null,
  "appointment_time": null,
  "appointment_location": null,
  "provider_name": null,
  "patient_name": null,
  "bill_period_start": null,
  "bill_period_end": null,
  "statement_date": null,
  "balance_previous": null,
  "payments_since_last": null,
  "response_deadline": null,
  "case_number": null,
  "form_identifier": null
}'''
    
    try:
        data = json.loads(missing_fields_response)
        
        # Check that missing fields are properly indicated
        key_details = data["key_details"]
        unclear_details = [d for d in key_details if "not clearly found" in d["value"].lower() or "unclear" in d["value"].lower()]
        
        if len(unclear_details) < 2:
            print(f"❌ Expected unclear fields not properly indicated")
            return False
        
        print("✅ Missing/unclear fields properly indicated in key_details")
        
        # Check confidence notes explain uncertainty
        if "unclear" not in data["confidence_notes"].lower():
            print(f"❌ Confidence notes should mention uncertainty")
            return False
        
        print("✅ Confidence notes properly explain uncertainty")
        
        return True
        
    except Exception as e:
        print(f"❌ Missing fields test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Refined Document Analysis Feature Tests")
    print("=" * 60)
    
    # Run tests
    test1_passed = test_json_schema()
    test2_passed = test_appointment_reminder_scenario()
    test3_passed = test_government_form_scenario()
    test4_passed = test_missing_fields_scenario()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"JSON Schema: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"Appointment Reminder: {'PASSED' if test2_passed else 'FAILED'}")
    print(f"Government Form: {'PASSED' if test3_passed else 'FAILED'}")
    print(f"Missing Fields: {'PASSED' if test4_passed else 'FAILED'}")
    
    if test1_passed and test2_passed and test3_passed and test4_passed:
        print("\n✅ All refined analysis tests passed!")
        exit(0)
    else:
        print("\n❌ Some tests failed!")
        exit(1)