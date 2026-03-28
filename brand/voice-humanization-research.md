# Voice Humanization Research

> Research-based guidelines to make AI captions sound human, not robotic.
> Compiled: March 2026

---

## The Problem: Why AI Writing Feels "Off"

Based on 2026 research from Grammarly, Medium, and AI detection experts:

| AI Signal | Why It Happens | Human Alternative |
|-----------|----------------|-------------------|
| **Low burstiness** | Uniform sentence lengths | Mix short punchy sentences with longer flowing ones |
| **Low perplexity** | Too predictable/obvious | Surprises, specificity, odd details |
| **Repetition** | Same words/phrases overused | Synonyms, varied vocabulary |
| **Lack of voice** | Generic, could be anyone | Personal details, specific experiences |

---

## 🚨 AI WORDS TO BAN

These words are instant AI tells. **Never use them:**

### The "LinkedIn Robot" List
```
delve / delving / let's delve
tapestry
realm / in the realm of
landscape (especially "digital landscape")
foster / fostering
navigate / navigating
elevate / elevating
embark / embarked
embrace / embracing
```

### The "Corporate Speak" List
```
groundbreaking
invaluable
relentless
endeavor
enlightening
insights (as standalone noun)
esteemed
shed light
crucial
paramount
```

### The "Overused Connector" List
```
Furthermore
Moreover
Additionally
Thus (as sentence starter)
In conclusion
It's worth noting
```

---

## ⚠️ PUNCTUATION TELLS

### The Em Dash Problem

Research shows AI is **addicted to em dashes** (—). They're "baked into its DNA" from training data.

**Problem:**
> "This glaze creates unpredictable patterns—each piece is a surprise—the colors come alive in the kiln."

**Human alternatives:**
- Use periods. Make it two sentences.
- Use commas for simpler breaks
- Use parentheses for asides (like this)

**Rule:** Maximum ONE em dash per caption. Ideally zero.

---

## 🎯 SENTENCE STRUCTURE PATTERNS

### The "Dead Giveaway" Structure

AI loves this pattern:
> "Not only [X], but also [Y]."

> "It's not just [obvious thing] — it's [deeper thing]."

**Human alternative:** Just say it directly.
> "This glaze surprises me every time."

### Uniform Length Problem

AI produces sentences of similar length. Humans vary wildly.

**AI feel:**
> "This piece was thrown on the wheel. The glaze is tenmoku. It has beautiful variation. DM to purchase."
> (All ~6-8 words)

**Human feel:**
> "Tenmoku on a wheel-thrown vase. The glaze did this thing where it broke at the rim—almost black there, rust-colored everywhere else. DM if you want it."
> (Short, long, medium. Natural rhythm.)

---

## ✅ HUMANIZATION PATTERNS

### 1. Specificity Over Generality

| AI Generic | Human Specific |
|------------|----------------|
| "beautiful texture" | "the glaze crawled and left these little bare spots" |
| "unique piece" | "this is the only bud vase that survived the kiln disaster" |
| "handmade with care" | "spent way too long on this foot" |
| "perfect for your home" | "holds exactly one very large coffee" |

### 2. Imperfection Signals

Humans include:
- Uncertainty ("I think this might be my favorite")
- Process struggles ("finally got the handle right on attempt 4")
- Humor at own expense ("wobbly but charming")
- Real timeframes ("three weeks from lump to this")

### 3. Conversational Fillers (Use Sparingly)

Natural human speech includes occasional:
- "honestly"
- "tbh"
- "funny story"
- "plot twist"
- "so yeah"
- "anyway"

**Rule:** 0-1 per caption max. Don't overdo.

### 4. Questions That Feel Real

| AI Generic | Human Real |
|------------|------------|
| "What do you think?" | "Rate this glaze 1-10, be honest" |
| "Do you prefer matte or gloss?" | "Matte or glossy - I'm genuinely curious what camp you're in" |
| "Comment below!" | "Drop a 🔥 if this is your vibe" |

---

## 🏺 CERAMICS-SPECIFIC HUMAN VOCABULARY

### Words That Sound Like a Potter Wrote Them

**Instead of "beautiful"** →
- satisfying
- clean
- chunky
- delicate
- heavy (in a good way)
- the way it sits
- nice weight
- feels good in the hand

**Instead of "unique"** →
- one of one
- this one's got personality
- never made another like it
- didn't turn out how I planned (and that's okay)

**Instead of "texture"** →
- tooth
- grain
- the way it catches light
- you can feel where my hands were

**Instead of "color variation"** →
- the glaze did its thing
- breaking at the edges
- darker where it pooled
- that spot where it thinned out

### Kiln/Firing Language

Real potters say:
- "kiln opening" not "kiln reveal"
- "cone 10" not "high fire"
- "reduction" not "special atmosphere"
- "came out of the kiln" not "emerged from firing"
- "gas kiln surprises" not "unpredictable results"

---

## 📝 HOOK PATTERNS THAT WORK

Research from 2026 shows hooks fall into categories:

### The Specific Hook
> "Tenmoku glaze on B-Mix clay. The combo I didn't know I needed."

### The Process Hook
> "From lump to vase in 47 seconds (actually 3 hours)"

### The Vulnerability Hook
> "This one was supposed to be a bowl."

### The Question Hook
> "Scale of 1-10, how much do you love a good glaze crawl?"

### The Anti-Hook (works for pottery)
> "Just a vase. A really good one though."

---

## 🔧 IMPLEMENTATION GUIDELINES

### For AI Caption Generation

Add to system prompts:

```
VOICE RULES:
- NEVER use: delve, tapestry, realm, landscape, embrace, elevate, navigate, embark, foster
- Maximum 1 em dash per caption
- Vary sentence length dramatically (3-word minimum, 20-word maximum)
- Include one specific detail (dimension, time, attempt number)
- Sound like a potter talking to friends, not a brand talking to customers
- Imperfection is good. Mention process, struggle, surprise.
- Questions should be specific, not generic "what do you think?"
```

### Quality Check

After generation, check:
1. [ ] No banned words
2. [ ] Sentence lengths vary by >50%
3. [ ] At least one specific detail
4. [ ] Sounds like something you'd say out loud
5. [ ] Would a potter roll their eyes at this?

---

## RESEARCH SOURCES

- Grammarly: "How to Avoid AI Detection in Writing" (Feb 2026)
- Medium: "The Em Dash Dilemma" by Brent Csutoras
- Inc: "The Structure of This Sentence Is a Dead Giveaway"
- Reddit r/ChatGPT: "Most Common Words and Phrases Used by AI"
- LinkedIn: Katharine Gordon's "60 Words to Avoid"
