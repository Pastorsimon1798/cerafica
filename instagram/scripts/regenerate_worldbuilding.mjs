#!/usr/bin/env node
/**
 * Regenerate worldbuilding for all 10 series pieces.
 * Extracts JS from pipeline.html, fetches vision data from SQLite, generates, POSTs back.
 */
import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(__dirname, '..', 'human-door', 'feedback.db');
const PIPELINE_PATH = join(__dirname, '..', 'human-door', 'pipeline.html');
const API_BASE = 'http://localhost:8766';

// 1. Extract worldbuilding JS from pipeline.html
const html = readFileSync(PIPELINE_PATH, 'utf-8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error('Could not extract script from pipeline.html'); process.exit(1); }
const jsCode = scriptMatch[1];

// 2. Evaluate the JS (defines all functions in global scope)
eval(jsCode);

// 3. Load vision data from SQLite
const db = new Database(DB_PATH, { readonly: true });

const pieces = db.prepare(`
    SELECT sp.id, sp.photo, sp.planet_name, sp.series_id, sp.order_index
    FROM series_pieces sp
    ORDER BY sp.order_index
`).all();

console.log(`Found ${pieces.length} series pieces to regenerate.\n`);

for (const piece of pieces) {
    const baseName = piece.photo.replace(/\.\w+$/, '');

    // Get vision data (prefer Kimi model)
    const vr = db.prepare(`
        SELECT vr.mood, vr.primary_colors, vr.color_appearance,
               vr.surface_qualities, vr.form_attributes, vr.technique,
               vr.clay_type, vr.glaze_type, vr.hypotheses, vr.idea_seeds
        FROM vision_results vr
        JOIN photos p ON vr.photo_id = p.id
        WHERE p.filename LIKE ?
        ORDER BY
            CASE WHEN vr.model LIKE '%Kimi%2.5%Ollama%' THEN 0
                 WHEN vr.model LIKE '%Kimi%' THEN 1
                 WHEN vr.model LIKE '%Ollama%' THEN 2
                 ELSE 3 END
        LIMIT 1
    `).get(`%${baseName}%`);

    if (!vr) {
        console.log(`SKIP ${piece.planet_name} (${piece.photo}): no vision data`);
        continue;
    }

    // Parse JSON fields
    const vision = {
        mood: vr.mood || 'earthy',
        primary_colors: safeJsonParse(vr.primary_colors),
        secondary_colors: [],
        surface_qualities: safeJsonParse(vr.surface_qualities),
        form_attributes: safeJsonParse(vr.form_attributes),
        technique: vr.technique || '',
        clay_type: vr.clay_type || '',
        glaze_type: vr.glaze_type || '',
        hypotheses: safeJsonParse(vr.hypotheses),
        idea_seeds: safeJsonParse(vr.idea_seeds)
    };

    // Generate worldbuilding
    const wb = generateWorldbuilding(vision, piece.planet_name, vision.idea_seeds || null);

    // POST to API
    try {
        const resp = await fetch(`${API_BASE}/api/series-piece`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                series_id: piece.series_id,
                photo: piece.photo,
                planet_name: piece.planet_name,
                orbital_data: wb.orbitalData,
                surface_geology: wb.surfaceGeology,
                formation_history: wb.formationHistory,
                inhabitants: wb.inhabitants,
                generated_caption: wb.caption
            })
        });
        const result = await resp.json();

        // Check inhabitants quality
        const hasFeelings = wb.inhabitants.includes('WHAT IT FEELS LIKE');
        const hasCiv = wb.inhabitants.includes('INTELLIGENT LIFE');
        const civContent = wb.inhabitants.split('INTELLIGENT LIFE\n')[1]?.split('\n\n')[0] || '';

        console.log(`OK ${piece.planet_name} (${piece.photo})`);
        console.log(`   Breathability: ${wb.orbitalData.split('Breathability: ')[1]?.split('\n')[0] || 'unknown'}`);
        console.log(`   Life sections: ${hasFeelings ? 'feelings' : 'NO FEELINGS'}, ${hasCiv ? 'civ' : 'NO CIV'}`);
        console.log(`   Civ: ${civContent.substring(0, 80)}...`);
        console.log(`   Caption: ${wb.caption.substring(0, 80)}...`);
        console.log('');
    } catch (err) {
        console.error(`ERROR ${piece.planet_name}: ${err.message}`);
    }
}

db.close();
console.log('Done.');

function safeJsonParse(str) {
    if (!str) return [];
    try { return JSON.parse(str); }
    catch { return []; }
}
