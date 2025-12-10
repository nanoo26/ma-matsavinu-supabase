# MASTER DIRECTIVE TEMPLATE  
This template defines how to write tasks for **"The Second Agent"** (Claude Sonnet 4.5 inside VS Code).

Each task must be written by replacing the placeholder sections below.

---

# DIRECTIVE FOR "THE SECOND AGENT"

You must read and fully obey all rules from:
`ChatGPT_Agent_Project_Instructions.md`

## TASK
[הכנס כאן את תיאור המשימה שאתה רוצה שהסוכן השני יבצע]

## REQUIREMENTS
- RTL Hebrew UI for anything user-facing  
- Do NOT modify backend logic unless explicitly instructed  
- Full updated files only – no partial snippets  
- Code in English, UI text in Hebrew  
- Mobile-first design (max width 480px)  
- Use CSS variables from `:root`  
- No new dependencies unless approved  
- Security rules must be followed (no leaking secrets)

## OUTPUT FORMAT
1. Short English summary  
2. Full updated files in fenced code blocks  
3. No "..." omissions  
4. No diffs – each file must be complete  

## NOTES
- If a file referenced in the task does not exist, create it.  
- If the task is unclear, ask for clarification.  
