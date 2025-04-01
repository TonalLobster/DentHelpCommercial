import openai
from flask import current_app

def generate_summary(transcription_text):
    """
    Generate a structured summary of the dental consultation
    
    Args:
        transcription_text: The transcribed text from the consultation
        
    Returns:
        dict: A structured summary with extracted information
    """
    try:
        openai.api_key = current_app.config['OPENAI_API_KEY']
        
        # Define the prompt for the GPT model
        prompt = f"""
        Based on the following dental consultation transcription, extract and organize the information into a structured summary.
        Include these categories:
        1. Patient Complaints
        2. Clinical Findings
        3. Diagnosis
        4. Treatment Plan
        5. Follow-up Recommendations
        
        For each category, provide bullet points of the key information. If a category is not mentioned in the text, mark it as "Not mentioned".
        
        Transcription:
        {transcription_text}
        """
        
        # Call OpenAI API to generate the summary
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or another appropriate model
            messages=[
                {"role": "system", "content": "You are a dental professional assistant that extracts structured information from consultation transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # Process the response to extract the structured information
        summary_text = response.choices[0].message.content
        
        # Parse the summary text and convert to structured data
        # This is a simplified version - in a real app, you'd want more robust parsing
        sections = {
            "Patient Complaints": [],
            "Clinical Findings": [],
            "Diagnosis": [],
            "Treatment Plan": [],
            "Follow-up Recommendations": []
        }
        
        current_section = None
        
        for line in summary_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a section header
            for section in sections:
                if section in line or f"{section}:" in line:
                    current_section = section
                    break
                    
            # If we're in a section and this is a bullet point, add it
            if current_section and (line.startswith('-') or line.startswith('•')):
                item = line[1:].strip()
                sections[current_section].append(item)
        
        return sections
        
    except Exception as e:
        current_app.logger.error(f"Summary generation error: {str(e)}")
        # Return a basic structure in case of error
        return {
            "Patient Complaints": ["Error generating summary"],
            "Clinical Findings": [],
            "Diagnosis": [],
            "Treatment Plan": [],
            "Follow-up Recommendations": []
        }