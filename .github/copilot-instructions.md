- [x] Verify that the copilot-instructions.md file in the .github directory is created. (File generated via create_new_workspace instructions)

- [x] Clarify Project Requirements (Desktop Python/PySide6 app with local storage, dashboards, and detailed reports captured)

- [x] Scaffold the Project (Manual Python PySide6 project structure created)

- [x] Customize the Project (Implemented PySide6 desktop app with SQLite-backed orders, dashboards, and reports)

- [x] Install Required Extensions (No extensions needed)

- [x] Compile the Project (py -3 -m compileall .\hustlenest)

- [x] Create and Run Task (Configured VS Code task 'Run HustleNest' -> py -3 -m hustlenest.main)

- [ ] Launch the Project

- [ ] Ensure Documentation is Complete

Execution Guidelines
- Use available tools to track progress through this checklist and update status after completing each step.
- Avoid verbose explanations or printing full command outputs; note skipped steps briefly.
- Stay concise when communicating project structure or decisions unless further detail is requested.

Development Rules
- Use '.' as the working directory unless otherwise specified.
- Avoid adding media or external links unless explicitly requested.
- Use placeholders only when necessary and call out that they require replacement.
- Use the VS Code API tool exclusively for VS Code extension projects.
- Do not suggest reopening the project in Visual Studio once it is already open in VS Code.
- Follow additional project setup rules when provided.

Folder Creation Rules
- Treat the current directory as the project root.
- When running terminal commands, include '.' to enforce the current working directory.
- Refrain from creating new folders unless explicitly requested, aside from a .vscode folder for tasks.json.
- If scaffolding commands report an incorrect folder name, ask the user to create the proper directory and reopen it in VS Code.

Extension Installation Rules
- Install only the extensions specified by get_project_setup_info recommendations.

Project Content Rules
- Assume a "Hello World" baseline when project details are unspecified.
- Avoid adding links or integrations unless they are directly required.
- Do not generate media assets unless explicitly requested.
- Flag placeholder media assets so users know to replace them.
- Ensure all generated components have a clear purpose aligned with user workflows.
- Ask for clarification before implementing unconfirmed features.
- When building a VS Code extension, consult the VS Code API tool for relevant guidance.

Task Completion Rules
- Consider work complete when the project scaffolding and compilation succeed without errors, the copilot-instructions.md file exists, the README.md file is current, and the user has clear run or debug guidance.
- Update progress before starting new tasks.

- Work through each checklist item systematically.
- Keep communication concise and focused.
- Follow development best practices.
