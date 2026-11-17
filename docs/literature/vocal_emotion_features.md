# How emotions sound — acoustic features per emotion (literature review)

Date: 2026-11-17. Status: draft for the researcher's review.

## Why

The robot will express its reaction through **three channels** — face
(EmotionsLibrary.kt), voice (prosody of the spoken reply) and text (the
words of the reply) — and the participant is asked which emotion the robot
felt. For the voice channel to carry the emotion, the robot's speech has to
change the way human speech does. This review collects, for each of the
robot's 11 emotions, the 4–7 acoustic features that the literature links to
it and the direction each one moves relative to neutral speech.

## The core papers

Five papers carry most of the table; the rest fill in the emotions the
classic studies did not cover.

| # | Paper | What it contributes |
|---|---|---|
| [1] | Banse & Scherer (1996), *Acoustic profiles in vocal emotion expression*, J. Personality and Social Psychology | 224 actor portrayals of **14 emotions** (incl. boredom, contempt, disgust, elation) analysed acoustically; vocal parameters index both arousal and valence; discriminant analysis confusions mirror human listeners'. |
| [2] | Juslin & Laukka (2003), *Communication of emotions in vocal expression and music performance: Different channels, same code?*, Psychological Bulletin | Meta-analysis of **104 vocal studies**: emotion-specific cue patterns (rate, intensity, F0 level/variability, contour, high-frequency energy, voice onsets, micro-irregularity) for anger, fear, happiness, sadness, tenderness. |
| [3] | Murray & Arnott (1993), *Toward the simulation of emotion in synthetic speech*, J. Acoustical Society of America | Review written **for speech synthesis**: three parameter families (voice quality, timing, pitch contour) per emotion — the most directly usable source for a talking robot. |
| [4] | Scherer (1986), *Vocal affect expression: A review and a model for future research*, Psychological Bulletin | The component-process predictions (tense vs. lax voice) behind [1] and [2]. |
| [5] | Pell et al. (2009), *Factors in the recognition of vocally expressed emotions: A comparison of four languages*, J. Phonetics | Six emotions incl. **pleasant surprise** in English, German, Hindi and Arabic; F0 level and variability matter in every language. |

Supporting papers: [6] Liu & Pell (2012, Mandarin, incl. surprise and
disgust); [7] Kamiloglu et al. (2020, review of 108 studies on positive
emotions); [8] Carl et al. (2022, **Hebrew**, English and German T-RES
sentences — mean F0 and speech rate separate anger, happiness and sadness in
Hebrew too); [9] Schewski et al. (2025, systematic review of negative
emotions — consistent for anger, **no consistent pattern for fear**);
[10] Ekberg et al. (2023, Swedish — surprise most acoustically distinct);
[11] de Aguiar et al. (2025, Brazilian Portuguese — surprise highest F0);
[12] Stevenson et al. (2025, theatre actors — tenderness as low activity);
[13] Warthe et al. (2022, acute sleep deprivation — F0, range, shimmer, HNR);
[14] Krajewski et al. (2009, acoustic sleepiness detection — prosody,
pauses, voice quality); [15] Larrouy-Maestri et al. (2024) and [16] van Rijn
et al. (2023) on the limits of a single global mapping.

## The features

| Feature | What it is |
|---|---|
| **Pitch level** | mean fundamental frequency (F0) |
| **Pitch range / variability** | F0 range or SD — how melodic vs. flat |
| **Loudness** | mean intensity |
| **Tempo** | speech / articulation rate |
| **Pauses** | number and length of pauses |
| **Contour** | direction of pitch movement, esp. at phrase ends |
| **Voice quality** | spectral balance (high-frequency energy = "sharp/tense" vs. "soft"), breathiness, jitter/shimmer, harmonics-to-noise ratio (HNR) |
| **Voice onsets** | how abruptly syllables start |

↑ higher / more than neutral, ↓ lower / less, ↕ the studies disagree.

## Per emotion

### Anger (כעס) — strong evidence

| Feature | Direction | Sources |
|---|---|---|
| Loudness | ↑ (much louder, more loudness variation) | [2] [3] [9] |
| Pitch level | ↑ | [2] [3] [9] |
| Pitch variability | ↑ (wide range) | [2] [3] |
| Tempo | ↑ (fast) | [2] [9] |
| Voice quality | tense, more high-frequency energy | [2] [4] |
| Voice onsets | fast, abrupt on stressed syllables | [2] [3] |

Confirmed in Hebrew sentences (F0 and rate) [8].

### Happiness (שמחה) — strong evidence

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↑ | [2] [3] [7] |
| Pitch variability | ↑ (wide, melodic) | [2] [3] [7] |
| Loudness | ↑ (medium-high, variable) | [2] [7] |
| Tempo | ↑ (moderately fast) | [2] |
| Contour | rising, smooth upward inflections | [2] [3] |
| Voice quality | brighter: higher first two formants (smiling) | [7] |

Confirmed in Hebrew sentences [8].

### Sadness (עצב) — strong evidence

| Feature | Direction | Sources |
|---|---|---|
| Tempo | ↓ (slow) | [2] [3] |
| Pitch level | ↓ | [2] [3] |
| Pitch variability | ↓ (flat, narrow) | [2] [3] |
| Loudness | ↓ | [2] [3] |
| Contour | falling | [2] [3] |
| Voice quality | less high-frequency energy; breathier, less harmonic | [2] [3] |
| Pauses | ↑ (longer) | [12] |

Confirmed in Hebrew sentences [8].

### Fear (פחד) — mixed evidence

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↑ (very high) | [2] [3] |
| Tempo | ↑ (fast) | [2] [3] |
| Pitch variability | ↕ (wider in [3], narrower in [2]) | [2] [3] |
| Loudness | ↕ (lower in [2] except panic; normal in [3]) | [2] [3] |
| Voice quality | irregular voicing (jitter), less high-frequency energy | [2] [3] |
| Contour | rising | [2] |
| Articulation | precise | [3] |

Caution: a recent systematic review found **no consistent acoustic pattern
for fear** [9], and actors portray it in both high- and low-activity ways
[12]. The same weakness the face check found (fear vs. surprise) exists in
the voice.

### Surprise (הפתעה) — moderate evidence (most studies: "pleasant surprise")

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↑ (highest of all emotions in several corpora) | [5] [6] [11] |
| Pitch variability | ↑ | [5] [6] |
| Loudness variability | ↑ | [6] [10] |
| Contour | high, rising phrase end | [5] [10] |
| Timing | distinctive temporal pattern (short, abrupt) | [10] |

### Disgust (גועל) — moderate evidence

| Feature | Direction | Sources |
|---|---|---|
| Tempo | ↓ (very slow; slowest in several corpora) | [3] [5] [11] |
| Pitch level | ↓ | [3] [6] |
| Pitch variability | ↓ (small) | [6] |
| Loudness | ↓ | [3] [6] |
| Voice quality | "grumbled", chest voice | [3] |
| Contour | wide downward inflections at phrase ends | [3] |

Disgust is among the least recognised emotions in speech [1] [6].

### Contempt (בוז) — weak evidence

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↓ | [1] |
| Loudness | ↓ | [1] |
| Tempo | ↓ | [1] |
| Contour | falling | [1] [4] |

Only [1] studied contempt acoustically among these papers, and it was
recognised poorly there. **To verify against [1]'s tables before use.**

### Excited (התלהבות) — strong evidence (= high-arousal joy / "elation")

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↑↑ (higher than calm happiness) | [1] [7] |
| Pitch variability | ↑↑ | [1] [7] |
| Loudness | ↑ (loud, variable) | [1] [7] |
| Tempo | ↑ (fast) | [1] [2] |
| Voice quality | more high-frequency energy, higher formants | [7] |

### Calm (רוגע) — moderate evidence (closest studied state: tenderness / contentment)

| Feature | Direction | Sources |
|---|---|---|
| Tempo | ↓ (slow) | [2] [12] |
| Loudness | ↓ (soft) | [2] [12] |
| Pitch level | ↓ / moderate | [2] [7] |
| Pitch variability | ↓ (little) | [2] |
| Contour | falling | [2] |
| Voice quality | soft (little high-frequency energy), regular | [2] [12] |
| Pauses | ↑ (longer) | [12] |

### Bored (שעמום) — moderate evidence

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↓ | [1] [4] |
| Pitch variability | ↓ (monotone) | [1] [4] |
| Loudness | ↓ | [1] |
| Tempo | ↓ (slow) | [1] |
| Voice quality | lax | [4] |

### Sleepy (עייפות) — evidence from fatigue research, not emotion portrayal

| Feature | Direction | Sources |
|---|---|---|
| Pitch level | ↓ | [13] |
| Pitch range | ↓ | [13] |
| Speech time / tempo | longer speech time (slower) | [13] |
| Voice quality | shimmer ↑, HNR ↓ (rougher, less clear) | [13] |
| Prosody / pauses | changed slow prosodic modulation and pause patterns | [14] |

## What this means for the robot

1. **Arousal is carried best.** Pitch level, loudness and tempo separate
   high-arousal (anger, happiness, excited, surprise, fear) from low-arousal
   (sadness, calm, bored, sleepy) emotions reliably. Emotions with the same
   arousal are harder to tell apart by voice alone — e.g. bored / sleepy /
   sad, or anger / happiness (Swedish: no parameter separated them [10]).
   This is the case for combining voice with face and text.
2. **The mapping isn't universal.** Individual, cultural and sex differences
   weigh more than one global mapping [16], and the acoustics-to-emotion
   mapping is "still unclear" after three decades [15]. The table is a
   starting point; the robot's voice needs its own listener check, like the
   face check in `furhat-emotion-study/expression_validation`.
3. **Hebrew:** only anger, happiness and sadness have been validated in
   Hebrew here [8]; the rest of the table rests on other languages.
4. **Implementation:** the voice must be controllable per line. Furhat's
   ElevenLabs voices ignore prosody (checked 2026-11-16). Google Chirp 3 HD
   (he-IL Aoede/Charon), measured 2026-11-17:
   - **rate** — works (`speakingRate`, or SSML `<prosody rate>`);
   - **loudness** — works and is exact (SSML `volume="+6dB"` doubled the RMS);
   - **pitch level** — the `pitch` parameter is refused ("This voice does not
     support pitch parameters"), but SSML `<prosody pitch>` moves F0 in the
     right direction, imprecisely (+4 st requested -> about +2 st measured,
     -4 st -> about -4 st; median F0 over 3 runs each), and the generative
     voice varies run to run;
   - **pitch range, voice quality, onsets** — not controllable;
   - `[pause]` markup — not supported for he-IL.
   So of the 4–7 features per emotion, rate, loudness, pitch level and a
   final rise/fall can be set; the rest needs a prompt-steerable model
   (Gemini-TTS, needs Vertex AI access) if it turns out to matter.
   First-draft profiles and samples: `~/Desktop/emotion_voice_samples/`
   (`profiles.json`), for the researcher to listen to.
   **Researcher decision (2026-11-17), after listening:** pitch shifts of
   +/-2-5 semitones made the voice sound like a different person, which
   people don't do. v2 profiles (`v2_rate_led/profiles_v2.json`) keep pitch
   within +/-1 semitone (sentence end included) and let **tempo** carry the
   emotion (65% sleepy ... 130% fear/excited), loudness as before. Charon
   (male) didn't sound good; the 16 male Chirp 3 HD voices were rendered for
   a new choice (`male_voices/`).
5. **Methodology:** adding the voice channel changes what the participant
   judges in the PE question (face + voice + text instead of face + text).
   That is a design decision to agree before data collection.

## References

1. Banse, R., & Scherer, K. R. (1996). [Acoustic profiles in vocal emotion expression.](https://consensus.app/papers/details/w:1ab15f6f-3fa3-415b-9a68-c99dc1ea81b2/?utm_source=claude_desktop) *Journal of Personality and Social Psychology.*
2. Juslin, P. N., & Laukka, P. (2003). [Communication of emotions in vocal expression and music performance: Different channels, same code?](https://consensus.app/papers/details/w:56c28184-bf74-44a9-ba21-d7a1d8880d8d/?utm_source=claude_desktop) *Psychological Bulletin.*
3. Murray, I. R., & Arnott, J. L. (1993). [Toward the simulation of emotion in synthetic speech: A review of the literature on human vocal emotion.](https://consensus.app/papers/details/w:de29f278-337a-4e40-8d4f-846e511e40ec/?utm_source=claude_desktop) *Journal of the Acoustical Society of America.*
4. Scherer, K. R. (1986). [Vocal affect expression: A review and a model for future research.](https://consensus.app/papers/details/w:a6546879-5cf7-406f-b215-b5cef29d812b/?utm_source=claude_desktop) *Psychological Bulletin.*
5. Pell, M. D., et al. (2009). [Factors in the recognition of vocally expressed emotions: A comparison of four languages.](https://consensus.app/papers/details/w:ef7e1810-862a-4c1e-b0db-c1e59cc1adf2/?utm_source=claude_desktop) *Journal of Phonetics.*
6. Liu, P., & Pell, M. D. (2012). [Recognizing vocal emotions in Mandarin Chinese: A validated database of Chinese vocal emotional stimuli.](https://consensus.app/papers/details/w:f67a8630-3495-4134-acf8-5df8b45e836c/?utm_source=claude_desktop) *Behavior Research Methods.*
7. Kamiloglu, R. G., et al. (2020). [Good vibrations: A review of vocal expressions of positive emotions.](https://consensus.app/papers/details/w:0c005d55-1892-41ef-b485-f71d24e490bc/?utm_source=claude_desktop) *Psychonomic Bulletin & Review.*
8. Carl, M., et al. (2022). [A cross-linguistic validation of the Test for Rating Emotions in Speech: Acoustic analyses of emotional sentences in English, German, and Hebrew.](https://consensus.app/papers/details/w:a9d3d0de-7244-45b5-97ca-2677bf1506a2/?utm_source=claude_desktop) *Journal of Speech, Language, and Hearing Research.*
9. Schewski, L., et al. (2025). [Measuring negative emotions and stress through acoustic correlates in speech: A systematic review.](https://consensus.app/papers/details/w:0d3091a4-46bd-42ac-bb12-b8047a887cd7/?utm_source=claude_desktop) *PLoS ONE.*
10. Ekberg, M., et al. (2023). [Acoustic features distinguishing emotions in Swedish speech.](https://consensus.app/papers/details/w:c1e4de12-cff2-4d35-a778-7bb8cc648786/?utm_source=claude_desktop) *Journal of Voice.*
11. de Aguiar, A. C., et al. (2025). [Medidas acústico-prosódicas discriminam as emoções de falantes do português brasileiro.](https://consensus.app/papers/details/w:24d8b39a-3ee2-4835-a4aa-5d02641a3474/?utm_source=claude_desktop) *CoDAS.*
12. Stevenson, T., et al. (2025). [The acoustic profiles of emotion: Analyzing the spoken voice in theater performance.](https://consensus.app/papers/details/w:1cb99186-3da0-4668-a7ac-b6712e6cbd96/?utm_source=claude_desktop) *Voice and Speech Review.*
13. Warthe, A. B., et al. (2022). [Changes in speech and voice characteristics following two hours and eight hours of acute sleep deprivation.](https://consensus.app/papers/details/w:24d46e03-8e1d-4d9b-9e8e-9271351ee2f0/?utm_source=claude_desktop) *Indian Journal of Aerospace Medicine.*
14. Krajewski, J., et al. (2009). [Acoustic sleepiness detection: Framework and validation of a speech-adapted pattern recognition approach.](https://consensus.app/papers/details/w:61db50a6-a097-4016-8b99-e3dd2f1157d6/?utm_source=claude_desktop) *Behavior Research Methods.*
15. Larrouy-Maestri, P., et al. (2024). [The sound of emotional prosody: Nearly 3 decades of research and future directions.](https://consensus.app/papers/details/w:d02533ba-fe8b-4ee5-a3a9-fc95390c8044/?utm_source=claude_desktop) *Perspectives on Psychological Science.*
16. van Rijn, P., et al. (2023). [Modelling individual and cross-cultural variation in the mapping of emotions to speech prosody.](https://consensus.app/papers/details/w:97f2fb55-aef2-4fc4-95b7-790c30567cb1/?utm_source=claude_desktop) *Nature Human Behaviour.*

Note: directions for each emotion are summarised from the papers' abstracts
and their reported profiles; the per-feature effect sizes should be checked
against the full texts (especially [1] for contempt and [2]'s cue table)
before they are quoted in the thesis.
