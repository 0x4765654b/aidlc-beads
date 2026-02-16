<!-- beads-issue: gt-6 -->
<!-- beads-review: gt-11 -->
# User Personas

## Persona 1: Alex -- Solo Developer / AI Agent Operator

- **Role**: Full-stack developer who uses AI agents to accelerate development
- **Technical Level**: High. Comfortable with CLI tools, Docker, Git, Python, AWS
- **Goals**: Manage one or more software projects end-to-end with AI assistance; review AI-generated artifacts and code; maintain quality control while minimizing manual work
- **Pain Points**: Context switching between tools; losing track of multi-project progress; having to manually coordinate AI workflows
- **Primary Interface**: Harmbe Dashboard (Chat Panel, Project Status), `gt` CLI for quick operations
- **Frequency**: Daily, multiple sessions

## Persona 2: Morgan -- Non-Technical Reviewer / Product Owner

- **Role**: Product owner or stakeholder who reviews requirements, designs, and business logic but does not write code
- **Technical Level**: Low. Comfortable with web browsers and document editing; not comfortable with CLI or Git
- **Goals**: Review and approve AIDLC artifacts (requirements, user stories, designs); provide feedback on business logic; track project progress without learning developer tools
- **Pain Points**: Needing to understand Git or CLI to participate; lack of visibility into project status; not knowing when action is needed
- **Primary Interface**: Outline Wiki (document review + action buttons), Harmbe Dashboard (Notification Center)
- **Frequency**: Weekly, triggered by review gate notifications

## Persona 3: Jordan -- Team Lead / Multi-Project Manager

- **Role**: Engineering lead overseeing multiple projects using Gorilla Troop
- **Technical Level**: Medium-High. Can use CLI and dashboard but prefers visual overview
- **Goals**: Monitor progress across all active projects; identify bottlenecks (stuck review gates, unanswered Q&As); prioritize and re-prioritize work; unblock teams quickly
- **Pain Points**: No single view of all project statuses; having to check each project individually; delayed awareness of blockers
- **Primary Interface**: Harmbe Dashboard (Multi-Project Sidebar, Project Status Panel, Notification Center)
- **Frequency**: Daily, brief check-ins
