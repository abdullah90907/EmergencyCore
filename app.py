import os
import gradio as gr
import requests
import json
from datetime import datetime

class EmergencyCore:
    """
    Advanced disaster response system with comprehensive emergency management capabilities.
    """
    
    def __init__(self, api_key):
        """
        Initialize the EmergencyCore with API credentials.
        
        Args:
            api_key (str): API key for external service authentication
        """
        self.xai_api_key = api_key

    def analyze_report(self, report_text, urgency):
        """
        Enhanced emergency report analysis using Grok API.
        
        Args:
            report_text (str): Detailed emergency situation description
            urgency (str): Urgency level of the report
        
        Returns:
            str: Formatted emergency analysis report
        """
        if not report_text:
            return "🚨 Error: Please provide a detailed emergency description."

        try:
            headers = {
                "Authorization": f"Bearer {self.xai_api_key}",
                "Content-Type": "application/json"
            }
            
            # Enhanced prompt with more context and specific instructions
            enhanced_prompt = f"""
            Advanced Disaster Analysis Protocol:
            
            Emergency Report: '{report_text}'
            Urgency Level: {urgency}

            Comprehensive Analysis Requirements:
            1. Identify precise disaster type
            2. Provide detailed severity assessment
            3. Outline immediate safety recommendations
            4. Develop comprehensive emergency response strategy
            5. Suggest resource allocation and prioritization

            Analyze with scientific precision and humanitarian insight.
            """
            
            payload = {
                "model": "grok-beta",
                "max_tokens": 500,
                "system": "You are an advanced AI disaster response coordinator with expertise in emergency management, risk assessment, and humanitarian aid.",
                "messages": [
                    {
                        "role": "user",
                        "content": enhanced_prompt
                    }
                ]
            }
            
            response = requests.post(
                "https://api.x.ai/v1/chat/completions", 
                headers=headers, 
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                
                # Urgency color coding
                urgency_prefix = {
                    "Low": "🟢",
                    "Medium": "🟠",
                    "High": "🔴"
                }
                
                # Format the analysis
                formatted_analysis = (
                    f"{urgency_prefix.get(urgency, '🚨')} {urgency.upper()} THREAT LEVEL\n\n"
                    f"{self._format_emergency_analysis(analysis)}"
                )
                
                return formatted_analysis
            else:
                return f"🚨 API Error: {response.status_code} - {response.text}"
        
        except requests.RequestException as e:
            return f"🚨 Network Error: {str(e)}"
        except Exception as e:
            return f"🚨 Critical Error: {str(e)}"

    def _format_emergency_analysis(self, analysis_text):
        """
        Advanced formatting of emergency analysis report.
        
        Args:
            analysis_text (str): Raw analysis text from API
        
        Returns:
            str: Formatted analysis report
        """
        def create_section(title, content):
            """
            Create a formatted section for the analysis.
            
            Args:
                title (str): Section title
                content (str): Section content
            
            Returns:
                str: Formatted section
            """
            formatted_lines = [
                f"🔍 {title.upper()}",
                "-" * 50
            ]
            
            # Process content lines
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    formatted_lines.append(f"   • {line[1:].strip()}")
                elif line:
                    formatted_lines.append(f"   {line}")
            
            return '\n'.join(formatted_lines)

        # Sections to extract and format
        sections = [
            "Potential Disaster Type Classification",
            "Severity Assessment",
            "Recommended Emergency Response",
            "Resource Allocation Suggestions"
        ]

        # Build formatted report
        formatted_report = [
            "🚨 EMERGENCY RESPONSE ANALYSIS 🚨",
            "=" * 40
        ]

        # Extract and format each section
        for section in sections:
            if section.lower() in analysis_text.lower():
                # Find the section content
                start = analysis_text.lower().find(section.lower())
                end = analysis_text.find('####', start + 1) if analysis_text.find('####', start + 1) != -1 else len(analysis_text)
                section_content = analysis_text[start:end].split('\n', 1)[1].strip()
                
                formatted_report.append('\n' + create_section(section, section_content))

        # Add timestamp and urgency note
        formatted_report.extend([
            "\n🕒 Analysis Timestamp: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "⚠️ URGENT ACTION REQUIRED ⚠️"
        ])

        return '\n'.join(formatted_report)

    def weather_prediction(self, location):
        """
        Enhanced weather prediction with detailed information.
        
        Args:
            location (str): Location for weather prediction
        
        Returns:
            str: Formatted weather prediction report
        """
        if not location:
            return "🌍 Error: Please enter a valid location."

        try:
            # Simulate more comprehensive weather prediction
            weather_risks = {
                "Low": "Minor weather concerns, standard precautions advised.",
                "Moderate": "Potential for severe weather. Prepare emergency kit and stay informed.",
                "High": "Extreme weather warning. Immediate protective actions recommended."
            }
            
            # Mock risk assessment (in real implementation, use a weather API)
            risk_level = "Moderate"
            
            return f"""🌦️ Weather Prediction for {location.title()}
Risk Level: {risk_level}
{weather_risks[risk_level]}

🕒 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⚠️ Always cross-check with local meteorological services"""
        
        except Exception as e:
            return f"🚨 Weather Prediction Error: {str(e)}"

    def upload_damage_image(self, image):
        """
        Enhanced image upload and processing.
        
        Args:
            image (PIL.Image): Uploaded image for damage assessment
        
        Returns:
            str: Image analysis report
        """
        if image is None:
            return "🖼️ No image uploaded. Please provide a damage assessment image."

        try:
            # Basic image metadata extraction
            height, width = image.size
            
            return f"""🖼️ Damage Assessment Image Analysis
Image Uploaded Successfully
📐 Dimensions: {width} x {height} pixels
📊 Processing Status: Preliminary assessment in progress
🔍 Recommendation: Detailed expert evaluation required

⚠️ Note: This is an automated initial assessment.
Full analysis requires professional on-site inspection."""
        except Exception as e:
            return f"🚨 Image Processing Error: {str(e)}"

    def create_interface(self):
      """
      Create an enhanced Gradio interface with improved visuals and interactivity.
      
      Returns:
          gr.Blocks: Configured Gradio interface
      """
      css = """
      .gradio-container {
          background-color: #f8fafc;
          font-family: 'Verdana', sans-serif;
          color: #333;
      }
      .analysis-output {
          background-color: #f0f9ff;
          border: 2px solid #007BFF;
          border-radius: 10px;
          padding: 15px;
          line-height: 1.6;
      }
      .gr-title {
          font-size: 24px;
          font-weight: bold;
          text-align: center;
          margin: 15px 0;
      }
      """

      with gr.Blocks(css=css) as demo:
          gr.Markdown("# 🚨 EmergencyCore: Advanced Disaster Response System")

          with gr.Tab("Emergency Reporting"):
              gr.Markdown("### 📝 Submit an Emergency Report")
              with gr.Row():
                  with gr.Column():
                      report_text = gr.Textbox(
                          label="Describe Emergency Situation", 
                          lines=6,
                          placeholder="Provide detailed information about the emergency (e.g., location, risks)..."
                      )
                      urgency = gr.Dropdown(
                          ["High", "Medium", "Low"], 
                          label="Urgency Level",
                          value="Medium"
                      )
                      submit_btn = gr.Button("Analyze Emergency 🚨", variant="primary")
                  
                  with gr.Column():
                      analysis_output = gr.Textbox(
                          label="Emergency Analysis", 
                          lines=15,
                          interactive=False,
                          elem_classes=["analysis-output"]
                      )
              
              submit_btn.click(
                  fn=self.analyze_report, 
                  inputs=[report_text, urgency], 
                  outputs=analysis_output
              )
          
          with gr.Tab("Weather Monitoring"):
              gr.Markdown("### 🌤️ Get Weather Predictions for Your Area")
              location_input = gr.Textbox(label="Enter Location")
              weather_btn = gr.Button("Get Weather Prediction 🌦️")
              weather_output = gr.Textbox(label="Weather Analysis", lines=8)
              
              weather_btn.click(
                  fn=self.weather_prediction, 
                  inputs=location_input, 
                  outputs=weather_output
              )
          
          with gr.Tab("Damage Assessment"):
              gr.Markdown("### 🖼️ Upload an Image for Damage Assessment")
              image_upload = gr.Image(
                  type="pil", 
                  label="Upload Damage Image",
                  height=300
              )
              image_output = gr.Textbox(
                  label="Image Analysis", 
                  lines=8,
                  interactive=False
              )
              
              process_btn = gr.Button("Process Damage Image 🔍")
              process_btn.click(
                  fn=self.upload_damage_image, 
                  inputs=image_upload, 
                  outputs=image_output
              )

          gr.Markdown(
              "#### 🔗 Learn More\n"
              "For help, visit our [FAQ page](https://example.com)."
          )

      return demo


def main():
    """
    Main function to initialize and launch EmergencyCore application.
    """
    # Replace with your actual Grok API key
    XAI_API_KEY = "xai-rBOk1AWqTKhnoSYs2N3icYx8aXu6wNDOK5qTapSJaNZz8QWP1zEEU0JflB9RuFuKRLEve2BG8g1kBs3P"
    
    # Create EmergencyCore instance
    emergency_core = EmergencyCore(XAI_API_KEY)
    
    # Create and launch the interface
    demo = emergency_core.create_interface()
    demo.launch(debug=True, share=True)

if __name__ == "__main__":
    main()


