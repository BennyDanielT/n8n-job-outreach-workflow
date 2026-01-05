# Geocodes

90009533: Greater Halifax Metropolitan Area
106120313: Bedford
Dartmouth, NS: 103703467
101174742: Canada
105149290: Ontario, Canada
100025096: Toronto, Canada
90009551: Greater Toronto Area
101788145: Mississauga, Canada
102199904: Calgary, Canada
106535873: Edmonton
4338859666: Vancouver, Canada
103644278: United States
106888327: Chennai, India
90009647: Greater Chennai Area
102713980: India



# facetCurrentFunction

13: Information Technology

# Examples:
facetCurrentFunction=13&facetGeoRegion=90009533 --> Information Technology & Services in Greater Halifax Metropolitan Area

# Fee fooo fum
CRITICAL VISUAL MATCHING REQUIREMENTS (NON-NEGOTIABLE):
1. HEADER (exact replica):
   - Name: HUGE, centered, small caps bold (Huge \scshape \textbf{})
   - Contact line: Canada | Phone icon | 782-882-2954 | Envelope icon | email (centered)
   - Links line: linkedin.com/in/bennydaniel616 |  maxeffortgazette.com |  bennydanielt.github.io (centered, clickable hyperlinks)

2. SECTION HEADERS: Bold, large, with black underline rule below (exactly like \titleformat{\section})

3. EXPERIENCE LAYOUT (exact \resumeSubheading structure):
   ```
   COMPANY NAME                    January 2025 - Present
   Software Developer              Halifax, Canada
   ```
   - Company name LEFT aligned, bold, large
   - Dates RIGHT aligned, bold, small
   - Role LEFT aligned (next line), italic, large  
   - Location RIGHT aligned, italic, small

EDUCATION (CRITICAL):
- Master's Degree ONLY: "Master of Applied Computer Science | Dalhousie University"
- Include CGPA exactly: "CGPA: 4.13/4.3"
- NO Bachelor's degree
- Use .education-entry class with flexbox layout matching experience

4. TECHNICAL SKILLS: Exact 2-column tabular layout:
**SKILLS TABLE (CRITICAL WRAPPING):**
Use .skills-table with .skills-row flexbox layout:
 Labels fixed width, values wrap naturally - NO icons, NO overflow
Don't include Kotlin as I am not an expert on it.

5. PROJECTS: Exact \resumeProjectHeading structure:
   ```
   AI Retrospective & Slack Notes Agent    Present
   ```
   - Project name LEFT, bold, large | Date RIGHT, bold, small

6. CERTIFICATIONS: Numbered list with inline wrapping
<ol class="cert-list">
  <li>AWS Certified Developer – Associate [Issued October 2023]</li>
  <li>AWS Certified Solutions Architect – Associate [Issued April 2023]</li>
</ol>


CONTENT CUSTOMIZATION RULES:
1. Preserve Benny's SMART-style metrics and detailed bullets (DO NOT oversimplify to one-liners)
2. Shorten slightly for 1-page fit but keep impact numbers and technologies
3. Reorder/replace 1-2 PROJECTS to match job stack/domain
4. Skills line at end of each experience role
5. Inject job keywords naturally into existing bullets

ONE-PAGE CONSTRAINT: Trim strategically (certifications first, then least relevant project, then bullet length)
h2 margin: 10px 0 2px

All section margins: 4-5px max

Bullet margins: 0.5px 0 2.5px

NO wasted vertical space

_____


Recipient Information:
- Name: {{ $json.recipientName }}
- Title: {{ $json.recipientTitle }}
- Company: {{ $json.recipientCompany }}
- Job they posted: {{ $json.jobTitle }}

Sender Information:
- Recent projects: {{ $json.userProjects }}