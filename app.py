# ESG Insights Code:
import streamlit as st
st.set_page_config(page_title="Aranca ESG Analyzer", layout="wide")
import fitz  # PyMuPDF for PDF extraction
import requests
import re
import io
from datetime import datetime
from streamlit_echarts import st_echarts
import streamlit.components.v1 as components
import base64
from bs4 import BeautifulSoup
from ESGComp import extract_data_from_html, generate_comparison_html
import pandas as pd
from xhtml2pdf import pisa
import os


# --- Email Whitelist ---
WHITELISTED_EMAILS = {
    "avinashg.singh@aranca.com",
    "avi104@yahoo.co.in",
    "ujjal.roy@aranca.com",
    "vishal.kumar@aranca.com",
    "rohit.dhawan@aranca.com"
}

# --- Email Verification ---
if "authorized" not in st.session_state:
    st.session_state["authorized"] = False

if not st.session_state["authorized"]:
    st.title("🔐 ESG Analyzer Login")
    user_email = st.text_input("Enter your email to proceed", placeholder="your@email.com")

    if st.button("🔓 Verify Email"):
        if user_email.strip().lower() in WHITELISTED_EMAILS:
            st.session_state["authorized"] = True
            st.session_state["user_email"] = user_email.strip()
            st.success("✅ Access granted! Please click on 'Verify Email' one more time to load the ESG Analyzer.")
        else:
            st.error("❌ Access denied. Email not verified.")

    # Stop rendering rest of app
    st.stop()


if st.session_state["authorized"]:


    # Try to import OCR libraries if available
    try:
        OCR_AVAILABLE = True
    except ImportError:
        OCR_AVAILABLE = False

    # DeepSeek API Settings (replace with your actual API key)
    DEEPSEEK_API_KEY = "sk-1288a478da4845fe99ea43ec5f1fc5de"
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


    def embed_logo_base64(logo_path="logo.png"):
        with open(logo_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"

    def extract_text_from_pdf(pdf_file):
        """Enhanced PDF text extraction with better error handling"""
        try:
            # Open the PDF file from memory
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            pdf_file.seek(0)  # Reset file pointer after reading

            text = []
            max_pages = 50  # Limit for very large documents

            for page_num, page in enumerate(doc):
                if page_num >= max_pages:
                    break
                try:
                    page_text = page.get_text("text")
                    if page_text.strip():
                        text.append(page_text)
                except Exception as e:
                    print(f"⚠️ Error reading page {page_num + 1}: {e}")

            full_text = "\n\n".join(text)
            if not full_text.strip():
                print("❌ Warning: No text found in PDF. Is this a scanned document?")
            return full_text
        except Exception as e:
            print(f"❌ Error reading PDF file: {e}")
            return ""

    def analyze_esg_with_deepseek(text):
        """Improved DeepSeek analysis with better prompting and error handling"""
        if not text.strip():
            print("❌ Error: Cannot send empty text to DeepSeek API!")
            return "DeepSeek API Error: No text provided."

        prompt = f"""
        You are an expert ESG analyst. Carefully read the following ESG disclosure and generate a detailed analysis. Be specific and data-driven.

        Provide the analysis in these sections:

        1. 🌍 **Environmental (E)**:
           - Give **10 detailed insights** about energy use, emissions, renewable energy adoption, waste reduction, water conservation, climate initiatives, biodiversity actions, etc.
           - Use **quantitative data**, clear targets, and named programs or initiatives.
           - Mention **year-over-year improvements** or regressions if applicable.
           - Avoid vague statements; elaborate where necessary.

        2. 🏢 **Social (S)**:
           - Give **10 detailed insights** covering labor practices, diversity & inclusion, community engagement, training programs, health & safety, etc.
           - Include **figures**, **employee stats**, and **notable case studies** if present.
           - Highlight notable changes over time and any certifications or recognitions.

        3. 🏛 **Governance (G)**:
           - Provide **10 robust insights** on board structure, executive compensation, risk management, ethics programs, whistleblower mechanisms, and audit independence.
           - Use **board diversity numbers**, policy names, or governance frameworks where mentioned.

        4. 🎤 **Key Management Remarks**:
           - Extract **5–10 strong quotes** from executive leadership, especially forward-looking or strategic statements.
           - Attribute each quote to a named executive or title if mentioned.

        5. 🎯 **ESG Sentiment Score**:
           - Rate from 1–10 (10 = exceptional ESG commitment and execution).
           - Justify score briefly in 1–2 lines by considering specificity, tone, and depth of ESG strategy.

        Return only the output in this structured format:
            ```
            Environmental:
            1. Insight 1...
            2. Insight 2...
            ...
            10. Insight 10...

            Social:
            1. Insight 1...
            ...
            10. Insight 10...

            Governance:
            1. Insight 1...
            ...
            10. Insight 1...

            Key Remarks:
            1. "Quote 1..." - [Title]
            2. "Quote 2..." - [Title]
            ...

            ESG Sentiment Score: X/10
            ```

        DOCUMENT TEXT:
        {text[:500000]}
        """

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 8000
        }

        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}, Response: {response.text}")
                return f"DeepSeek API Error: {response.status_code}"

            response_data = response.json()
            if "choices" in response_data:
                result = response_data["choices"][0]["message"]["content"]
                return result
            else:
                print("❌ Unexpected API response format")
                return "DeepSeek API Error: No insights generated."
        except Exception as e:
            print(f"❌ DeepSeek API Request Failed: {e}")
            return f"DeepSeek API Error: {str(e)}"

    def parse_esg_data(api_response):
        """Enhanced parsing with better error handling"""
        esg_data = {
            "environment": [],
            "social": [],
            "governance": [],
            "management_remarks": [],
            "sentiment_score": "N/A"
        }

        try:
            # Extract Environmental insights
            env_match = re.search(r'Environmental:\s*(.*?)(?=\n\s*Social:|$)', api_response, re.DOTALL)
            if env_match:
                env_insights = [i.strip() for i in env_match.group(1).split('\n') if i.strip()]
                esg_data["environment"] = [re.sub(r'^\d+\.\s*', '', i) for i in env_insights[:10]]

            # Extract Social insights
            soc_match = re.search(r'Social:\s*(.*?)(?=\n\s*Governance:|$)', api_response, re.DOTALL)
            if soc_match:
                soc_insights = [i.strip() for i in soc_match.group(1).split('\n') if i.strip()]
                esg_data["social"] = [re.sub(r'^\d+\.\s*', '', i) for i in soc_insights[:10]]

            # Extract Governance insights
            gov_match = re.search(r'Governance:\s*(.*?)(?=\n\s*Key Remarks:|$)', api_response, re.DOTALL)
            if gov_match:
                gov_insights = [i.strip() for i in gov_match.group(1).split('\n') if i.strip()]
                esg_data["governance"] = [re.sub(r'^\d+\.\s*', '', i) for i in gov_insights[:10]]

            # Extract Management Remarks
            mgmt_match = re.search(r'Key Remarks:\s*(.*?)(?=\n\s*ESG Sentiment Score:|$)', api_response, re.DOTALL)
            if mgmt_match:
                remarks = [i.strip() for i in mgmt_match.group(1).split('\n') if i.strip()]
                esg_data["management_remarks"] = [re.sub(r'^\d+\.\s*', '', i) for i in remarks[:10]]

            # Extract Sentiment Score
            sentiment_match = re.search(r'ESG Sentiment Score:\s*(\d+\.?\d*)\s*/\s*10', api_response)
            if sentiment_match:
                esg_data["sentiment_score"] = sentiment_match.group(1)

        except Exception as e:
            print(f"⚠️ Error parsing ESG data: {e}")

        return esg_data

    def score_esg_by_rubric(esg_data):
        """Evaluate ESG output based on rubric and return a score out of 10"""
        score = 0
        total_weight = 0

        def count_quantitative(insights):
            return sum(1 for i in insights if re.search(r"\d+[%$]|tons|kWh|CO2|GHG|employees|ISO|CDP|GRI", i, re.IGNORECASE))

        def count_specific(insights):
            return sum(1 for i in insights if len(i.split()) > 8)

        def count_named_programs(insights):
            return sum(1 for i in insights if re.search(r"\b(program|initiative|strategy|framework|plan|policy)\b", i, re.IGNORECASE))

        weights = {
            "quantitative": 2.5,
            "specificity": 2.5,
            "programs": 2.0,
            "quotes": 2.0,
            "certifications": 1.0
        }

        # Environmental + Social + Governance combined
        all_insights = esg_data["environment"] + esg_data["social"] + esg_data["governance"]

        # Quantitative insights
        quant_count = count_quantitative(all_insights)
        score += weights["quantitative"] if quant_count >= 5 else weights["quantitative"] * 0.4

        # Specificity
        specific_count = count_specific(all_insights)
        score += weights["specificity"] if specific_count >= 10 else weights["specificity"] * 0.5

        # Named programs/initiatives
        named_count = count_named_programs(all_insights)
        score += weights["programs"] if named_count >= 5 else weights["programs"] * 0.5

        # Management quotes
        quote_count = len(esg_data["management_remarks"])
        score += weights["quotes"] if quote_count >= 5 else weights["quotes"] * 0.5

        # Certifications
        cert_count = sum(1 for i in all_insights if re.search(r"\bISO|CDP|GRI\b", i, re.IGNORECASE))
        score += weights["certifications"] if cert_count >= 1 else weights["certifications"] * 0.2

        return round(score, 2)

    # ----------- Gauge Chart ----------- #
    def show_esg_gauge(score):
        option = {
            "tooltip": {
                "formatter": "{a} <br/>{b} : {c}/10"
            },
            "series": [{
                "name": "ESG Score",
                "type": "gauge",
                "min": 0,
                "max": 10,
                "splitNumber": 10,
                "axisLine": {
                    "lineStyle": {
                        "color": [[0.3, '#ff4c4c'], [0.7, '#ffbf00'], [1, '#00e676']],
                        "width": 18
                    }
                },
                "pointer": {
                    "width": 5,
                    "length": '70%'
                },
                "detail": {
                    "formatter": f"{score}/10",
                    "fontSize": 24,
                    "offsetCenter": [0, "80%"]
                },
                "data": [{"value": float(score), "name": "ESG Score"}]
            }]
        }
        st_echarts(option, height="360px")


    def generate_html_report(esg_data, company_name):
        """
        Creates an interactive HTML report with company name only
        Report name: ESG_Insights_<Company Name>.html
        Report title: <Company Name> ESG Insights Report
        """
        # Clean company name for filename
        safe_company_name = re.sub(r'[^\w\-_]', '_', company_name)[:50]
        logo_data_uri = embed_logo_base64("logo.png")
        output_file = f"ESG_Insights_{safe_company_name}.html"

        # Format current date
        current_date = datetime.now().strftime("%B %d, %Y")

        def generate_section(title, icon, insights):
            if not insights:
                return ""
            section_html = f"""
                <h2><span class="category-icon">{icon}</span>{title}</h2>
                <table>
                    <thead>
                        <tr>
                            <th width="5%">#</th>
                            <th>Insight</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for idx, insight in enumerate(insights, 1):
                section_html += f"""
                        <tr>
                            <td>{idx}</td>
                            <td>{insight}</td>
                        </tr>
                """
            section_html += """
                    </tbody>
                </table>
            """
            return section_html

        # Build the complete HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{company_name} ESG Insights Report</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f9f9f9;
                    padding: 0;
                    margin: 0;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 20px auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0,0,0,0.1);
                }}
                header {{
                    border-bottom: 2px solid #2196F3;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                h1 {{
                    margin-top: 0;
                    font-size: 2.2em;
                }}
                h2 {{
                    border-bottom: 1px solid #eee;
                    padding-bottom: 8px;
                    margin-top: 30px;
                    font-size: 1.5em;
                    color: #2196F3;
                }}
                h3.subtitle {{
                    color: #7f8c8d;
                    font-weight: normal;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    font-size: 0.95em;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px 15px;
                    text-align: left;
                }}
                th {{
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
                tr:hover {{
                    background-color: #e3f2fd;
                }}
                .sentiment {{
                    font-size: 1.2em;
                    padding: 10px 15px;
                    background-color: #e8f5e9;
                    border-radius: 4px;
                    display: inline-block;
                    margin: 10px 0;
                }}
                footer {{
                    margin-top: 40px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #7f8c8d;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }}
                .category-icon {{
                    font-size: 1.2em;
                    margin-right: 8px;
                }}
            </style>
        </head>
        <body>
        <div class="container">
            <img src="{logo_data_uri}" alt="Company Logo" style="height:30px; max-width:175px; margin-bottom:20px;">
                <header>
                    <h1>{company_name} ESG Insights Report</h1>
                    <h3 class="subtitle">Generated on: {current_date}</h3>
                    <div class="sentiment">
                        <strong>LLM Score:</strong> {esg_data.get('sentiment_score', 'N/A')}/10<br>
                        <strong>Rubric Score:</strong> {esg_data.get('rubric_score', 'N/A')}/10
                    </div>
                </header>
        """

        # Add sections
        html_content += generate_section("Environmental Insights", "🌍", esg_data["environment"])
        html_content += generate_section("Social Insights", "🏢", esg_data["social"])
        html_content += generate_section("Governance Insights", "🏛", esg_data["governance"])

        # Add management remarks if available
        if esg_data["management_remarks"]:
            html_content += """
                <h2>🎤 Key Remarks by Management</h2>
                <table>
                    <thead>
                        <tr>
                            <th width="5%">#</th>
                            <th>Remark</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for idx, remark in enumerate(esg_data["management_remarks"], 1):
                html_content += f"""
                        <tr>
                            <td>{idx}</td>
                            <td>{remark}</td>
                        </tr>
                """
            html_content += """
                    </tbody>
                </table>
            """

        # Footer
        html_content += f"""
                <footer>
                    ESG Insights Generated On {current_date}<br><br>
                    <strong>Contact:</strong> <a href="mailto:inquiry@aranca.com">inquiry@aranca.com</a> |
                    <a href="https://www.linkedin.com/in/your-profile" target="_blank">LinkedIn</a>
                </footer>

            </div>
        </body>
        </html>
        """

        # Create an in-memory file
        file_stream = io.BytesIO()
        file_stream.write(html_content.encode('utf-8'))
        file_stream.seek(0)

        # Send file as an attachment
        return file_stream, safe_company_name


    def updated_generate_esg_report(pdf_file, company_name):
        """
        Main function to generate ESG report with enhanced error handling
        """
        try:
            # Step 1: Extract text from PDF
            pdf_text = extract_text_from_pdf(pdf_file)
            if not pdf_text.strip():
                print("❌ Error: No text extracted from PDF")
                return False

            # Step 2: Analyze with DeepSeek
            esg_analysis = analyze_esg_with_deepseek(pdf_text)
            if "Error" in esg_analysis:
                print(f"❌ Analysis failed: {esg_analysis}")
                return False

            # Step 3: Parse results
            esg_data = parse_esg_data(esg_analysis)

            # Step 4: Apply rubric-based scoring
            rubric_score = score_esg_by_rubric(esg_data)
            esg_data["rubric_score"] = f"{rubric_score}"  # your score
            # DeepSeek score already exists in esg_data["sentiment_score"]


            # Step 5: Generate report
            report_file, safe_company_name = generate_html_report(esg_data, company_name)

            return safe_company_name, report_file  # Returning same format as generate_esg_report

        except Exception as e:
            print(f"❌ Fatal error in report generation: {e}")
            return False

    # --------------------------
    # ✅ STREAMLIT INTERFACE (Enhanced, Final)
    # --------------------------

    # --- Page Setup ---

    # Logo loader
    def get_base64_logo(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    logo_base64 = get_base64_logo("logo.png")

    # 🌙 Toggle for Dark Mode
    #dark_mode = st.toggle("🌙 Dark Mode", value=False)

    # Colors based on toggle
    bg_color = "#ffffff"
    text_color = "#212121"
    label_color = "#222"
    input_bg = "#ffffff"
    placeholder_color = "#999"
    card_bg = "#f9f9f9"



    # Inject CSS style
    st.markdown(f"""
    <style>
        html, body, .main {{
            background-color: #ffffff;
            color: #010101;
        }}
        .stButton > button {{
            background-color: #ffffff;
            color: black;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        .stButton > button:hover {{
            background-color: #2196F3 !important;
            color: white !important;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .streamlit-expanderHeader:hover {{
            color: #2196F3 !important;
            background-color: #f5f5f5 !important;
            cursor: pointer;
        }}
        .esg-box {{
            background-color: #f9f9f9;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 0 10px #ccc;
        }}
        .custom-footer {{
            position: fixed;
            bottom: 15px;
            width: 100%;
            text-align: center;
            color: #010101;
            font-size: 0.85em;
        }}
        a {{
            color: #1976d2;
        }}
        label, .stTextInput label, .stFileUploader label {{
            color: #222 !important;
            font-size: 1.2rem !important;
            font-weight: 600 !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 10px;
        }}
        input, .stTextInput input, .stFileUploader input {{
            font-size: 1rem !important;
            color: #222 !important;
            background-color: #fff !important;
            border: 1px solid #ccc !important;
        }}
        .stTextInput input::placeholder {{
            color: #999 !important;
        }}
        .stAlert, .stMarkdown, .css-1cpxqw2, .css-12ttj6m {{
            color: #010101 !important;
            font-size: 1.2rem;
        }}
        .streamlit-expanderContent {{
            color: #333 !important;
            font-size: 0.97rem !important;
        }}
        .esg-scorebox {{
            margin-top: 10px;
            padding: 10px;
            background: #f1f1f1;
            border-radius: 6px;
            font-size: 1rem;
            color: #222;
        }}


    /* Fix st.download_button styling */
    .css-ocqkz7, .stDownloadButton > button {{
        background-color: #ffffff !important;
        color: #010101 !important;
        font-weight: bold !important;
        border: 1px solid #ccc !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        font-size: 1.05rem !important;
        transition: background-color 0.3s ease, color 0.3s ease;
    }}

    .css-ocqkz7:hover, .stDownloadButton > button:hover {{
        background-color: #2196F3 !important;
        color: #ffffff !important;
        cursor: pointer !important;
    }}



    </style>

    <!-- HEADER: logo > title > subtitle -->
    <div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;">
        <img src="data:image/png;base64,{logo_base64}" style="height: 40px; max-width: 240px; margin-bottom: 10px;" />
        <h1 style="margin: 0; font-size: 2.6rem; color: #010101;">ESG Insights Dashboard</h1>
        <p style="margin: 6px 0 0 0; font-size: 1.1rem; color: #010101;">AI-powered ESG Analysis and Scoring</p>
    </div>
    """, unsafe_allow_html=True)

    # --- Input UI ---
    with st.container():
        company = st.text_input("🏢 Enter Company Name", placeholder="Type here...")
        file = st.file_uploader("📄 Upload ESG Disclosure PDF", type="pdf")

        if st.button("🚀 Generate ESG Report"):
            if not all([company, file]):
                st.error("Please enter a company name and upload a PDF file.")
            else:
                with st.spinner("Analyzing ESG disclosures..."):
                    text = extract_text_from_pdf(file)
                    response = analyze_esg_with_deepseek(text)
                    esg_data = parse_esg_data(response)

                    esg_data["rubric_score"] = score_esg_by_rubric(esg_data)
                    st.markdown(f"""
                        <div style='margin-top:10px;padding:10px;background:#010101;border-radius:6px'>
                            <b>LLM Score:</b> {esg_data['sentiment_score']} / 10<br>
                            <b>Rubric Score:</b> {esg_data.get('rubric_score', 'N/A')} / 10
                        </div>
                    """, unsafe_allow_html=True)

                    show_esg_gauge(float(esg_data["rubric_score"]))

                    with st.expander("🌍 Environmental Insights"):
                        for e in esg_data["environment"]: st.markdown(f"- {e}")
                    with st.expander("🏢 Social Insights"):
                        for s in esg_data["social"]: st.markdown(f"- {s}")
                    with st.expander("🏛 Governance Insights"):
                        for g in esg_data["governance"]: st.markdown(f"- {g}")
                    with st.expander("🎤 Management Remarks"):
                        for r in esg_data["management_remarks"]: st.markdown(f"> {r}")

                    html_file, filename = generate_html_report(esg_data, company)
                    html_content = html_file.read().decode("utf-8")

                    st.download_button(
                        label="📥 Download HTML Report",
                        data=html_content,
                        file_name=f"{filename}.html",
                        mime="text/html"
                    )

                    pdf_stream = convert_html_to_pdf(html_content)
                    if pdf_stream:
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_stream,
                            file_name=f"{filename}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.warning("⚠️ PDF export failed. Try downloading the HTML version.")

                    try:
                        log_entry = {
                            "email": st.session_state.get("user_email", "unknown"),
                            "company": company,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        df_log = pd.DataFrame([log_entry])
                        if not os.path.exists("access_log.csv"):
                            df_log.to_csv("access_log.csv", index=False)
                        else:
                            df_log.to_csv("access_log.csv", mode="a", header=False, index=False)
                    except Exception as log_err:
                        st.warning(f"Logging failed: {log_err}")


    def convert_html_to_pdf(html_content):
        """Converts HTML string to PDF and returns as BytesIO"""
        pdf_stream = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_stream)
        if pisa_status.err:
            return None
        pdf_stream.seek(0)
        return pdf_stream

    # --- Section: ESG Comparison Tool ---
    st.markdown("---")
    st.markdown("<h2 style='color:#010101;'>📊 ESG Comparison Tool</h2>", unsafe_allow_html=True)

    uploaded_html_files = st.file_uploader(
        "📂 Upload up to 5 ESG HTML Reports", type="html", accept_multiple_files=True
    )

    if st.button("🔍 Compare Reports"):
        if not uploaded_html_files:
            st.warning("Please upload at least one HTML file.")
        elif len(uploaded_html_files) > 5:
            st.warning("You can compare up to 5 ESG reports.")
        else:
            try:
                comparison_data = []
                for file in uploaded_html_files:
                    file_text = file.read().decode("utf-8")
                    soup = BeautifulSoup(file_text, 'html.parser')

                    def extract_insights(section_icon):
                        insights = []
                        section_header = soup.find(lambda tag: tag.name == 'h2' and section_icon in tag.get_text())
                        if section_header:
                            table = section_header.find_next('table')
                            if table:
                                rows = table.find_all('tr')[1:]
                                for row in rows:
                                    cells = row.find_all('td')
                                    if len(cells) >= 2:
                                        insights.append(cells[1].get_text(strip=True))
                        return insights[:10]

                    company_name = soup.find('h1').text.strip().replace("ESG Insights Report", "").strip()
                    sentiment_div = soup.find('div', class_='sentiment')
                    sentiment_score = "N/A"
                    if sentiment_div:
                        match = re.search(r'(\d+(\.\d+)?)/10', sentiment_div.get_text())
                        if match:
                            sentiment_score = match.group(1)

                    report_data = {
                        'company_name': company_name,
                        'sentiment_score': sentiment_score,
                        'environment': extract_insights("🌍"),
                        'social': extract_insights("🏢"),
                        'governance': extract_insights("🏛")
                    }
                    comparison_data.append(report_data)

                html_filename = generate_comparison_html(comparison_data)
                with open(html_filename, 'rb') as f:
                    st.download_button(
                        label="📥 Download ESG Comparison Report",
                        data=f,
                        file_name=html_filename,
                        mime="text/html"
                    )
            except Exception as e:
                st.error(f"❌ Error generating comparison: {str(e)}")

    # Footer
    st.markdown(f"""
    <div class="custom-footer">
        &copy; 2025 Aranca. Contact: <a href="mailto:inquiry@aranca.com">inquiry@aranca.com</a> |
        <a href="https://www.linkedin.com/company/aranca" target="_blank">LinkedIn</a>
    </div>
    """, unsafe_allow_html=True)







