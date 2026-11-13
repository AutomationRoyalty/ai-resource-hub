# Automation Specialist Kit

Build a landing page, an n8n automation and a Notion dashboard with one Claude prompt.

Tutorial: [How Claude SMOKED our $60k/yr "automation specialist"](https://www.youtube.com/watch?v=r9yh5yozq8s)

## What's inside
- `prompts/build-landing-page.txt`: the one prompt that builds everything
- `prompts/qc-agent.txt`: a daily check that pings you if something breaks
- `n8n/ai-optin-to-notion.json`: the opt-in workflow (paste it into n8n)
- `notion-optins-table.md`: the table columns, if you build it by hand

## Steps
1. Sign up for Claude (Pro or higher), Railway, Vercel and Notion.
2. In Railway, deploy the **n8n** template and create your n8n account.
3. In Claude Code, connect the **n8n**, **Vercel** and **Notion** connectors.
4. Paste `prompts/build-landing-page.txt` into Claude, with your own business and links.
5. Create a Notion API key, add it to the **Save to Notion** node in n8n, and tell Claude **credential added**.
6. Paste `prompts/qc-agent.txt` to get a daily health check.
