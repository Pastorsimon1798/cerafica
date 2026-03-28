# Photo Assets

Drag-and-drop target for photos from your phone (via AirDrop).

## Folder Map

```
assets/
├── available/   Pieces currently for sale → shop page + homepage featured
├── process/     Process/studio photos → about page + homepage process section
└── sold/        Archive of sold pieces
```

## Workflow

1. AirDrop photos from your phone to the appropriate folder
2. Rename files descriptively: `obsidian-orbiter.jpg`, `throwing-on-wheel.jpg`
3. Website HTML references these paths: `../assets/available/{filename}`
4. Photos are gitignored — only README.md files are tracked

## Conventions

- Use `.jpg` or `.png`
- Keep images under 2MB (optimize before dropping if needed)
- Square (1:1) or portrait (3:4) aspect ratio preferred
- Name with lowercase, hyphens, no spaces
