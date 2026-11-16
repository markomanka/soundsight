# Research base

The single entry point for the literature that grounds SoundSight's decisions.

Origin: the register, its identifiers and its maintenance rule were drafted by Kimi
(kimi.ai) in a session with the project lead on 2026-11-15. On review, every journal
article was checked against its PubMed record, two attributions were corrected, two
entries were added and four were retired. Changes are listed at the end.

## Rules

1. **No literature without a consumer.** An entry is added only together with the
   decision, experiment, gate or code that uses it, named in the "Used by" column.
   Consumers marked *planned* do not exist yet.
2. **Say how it was checked.** "PubMed" means title, authors, journal, volume and pages
   were compared with the PubMed record on the date given. "Unchecked" entries must be
   confirmed against the publisher before being cited outside this repository.
3. **Say what kind of evidence it is.** A review is not a study; a standard is not
   evidence that something works.
4. Decision records cite these identifiers on their "Literature:" line; CI checks that
   every identifier cited exists here (`tools/check_docs.py`).

## A. Human echolocation: abilities and training

| ID | Citation | Used by, and what we take from it | Kind | Checked |
| --- | --- | --- | --- | --- |
| A2 | Kolarik AJ, Cirstea S, Pardhan S, Moore BCJ (2014). A summary of research investigating echolocation abilities of blind and sighted humans. *Hearing Research* 310:60-68. doi:10.1016/j.heares.2014.01.010 | docs/roadmap.md, stage S2 (*planned* exercise specification): ranges of distance, size and position abilities used to set exercise difficulty. | Review | PubMed 2026-11-15 |
| A3 | Norman LJ, Dodsworth C, Foresteire D, Thaler L (2021). Human click-based echolocation: Effects of blindness and age, and real-life implications in a 10-week training program. *PLoS ONE* 16(6):e0252330. doi:10.1371/journal.pone.0252330 | EXP-0003 (disc diameters 5.1 to 25.4 cm at 33, 66, 99 cm are the canonical size-discrimination set); docs/roadmap.md S2 (template for the first exercise pack: size discrimination, orientation of an 80 x 20 cm rectangle, virtual maze navigation with W/A/S/D steps and 45 degree turns, mirror-image mazes to separate skill from rote learning, a no-click control condition, distance raised after two sessions at 90%); docs/quality/quality-gates.md (open question the paper itself names: whether computer-only training transfers to real navigation is untested). | Training study, 12 blind and 14 sighted adults, open data | PubMed full text 2026-11-15 |
| A4 | Dodsworth C, Norman LJ, Thaler L (2020). Navigation and perception of spatial layout in virtual echo-acoustic space. *Cognition* 197:104185. doi:10.1016/j.cognition.2020.104185 | docs/roadmap.md S2 and S3: virtual echo-acoustic navigation over headphones improves with training and generalises to untrained virtual spaces; three blind experts could do it untrained. Note the stimuli were binaural recordings in real corridors, not simulations. | Training study, 14 sighted adults | PubMed 2026-11-15 |
| A5 | Norman LJ, Hartley T, Thaler L (2024). Changes in primary visual and auditory cortex of blind and sighted adults following 10 weeks of click-based echolocation training. *Cerebral Cortex* 34(6):bhae239. doi:10.1093/cercor/bhae239 | docs/roadmap.md (premise): ten weeks of training changes sensory cortex in blind and sighted adults alike. | Imaging study, pre-post | PubMed 2026-11-15 |
| G1 | Tonelli A, Brayda L, Gori M (2016). Depth echolocation learnt by novice sighted people. *PLoS ONE* 11(6):e0156654. doi:10.1371/journal.pone.0156654 | docs/roadmap.md S2: novices judge depth above chance by the second session, and do better in a reverberant room than in an anechoic one, so room reverberation belongs in the exercises instead of being removed. | Training study, sighted novices | PubMed 2026-11-15 |

## B. Clicks and echoes

| ID | Citation | Used by, and what we take from it | Kind | Checked |
| --- | --- | --- | --- | --- |
| B1 | Thaler L, Reich GM, Zhang X, et al. (2017). Mouth-clicks used by blind expert human echolocators: signal description and model based signal synthesis. *PLoS Computational Biology* 13(8):e1005670. doi:10.1371/journal.pcbi.1005670 | src/soundsight/click/qc.py (provisional reference profile: about 3 ms, peak 2 to 4 kHz); src/soundsight/acoustics/canonical.py (click band); docs/decisions/0002; quality gate S1. Also gives the beam pattern (level roughly constant within a 60 degree cone) and a synthesis model for a later, more faithful `click synth`. | Measurement study, three experts | PubMed 2026-11-15 |
| B2 | Thaler L, De Vos R, Kish D, Antoniou M, Baker C, Hornikx M (2018). Human echolocators adjust loudness and number of clicks for detection of reflectors at various azimuth angles. *Proc. R. Soc. B* 285(1873):20172735. doi:10.1098/rspb.2017.2735 | EXP-0003 (a 17.5 cm disc at 100 cm is a measured detection case; echoes were detected down to 27 dB below the emission, a floor for how weak a simulated echo may be and still matter); docs/roadmap.md S2 (number and loudness of clicks as tracked behaviour). | Experiment, eight blind experts | PubMed 2026-11-15 |
| C1 | Castillo-Serrano JG, Norman LJ, Foresteire D, Thaler L (2021). Increased emission intensity can compensate for the presence of noise in human click-based echolocation. *Scientific Reports* 11:1750. doi:10.1038/s41598-021-81220-9 | docs/roadmap.md S2 (noise-ladder exercises): echoes needed about 12 dB more spectral power than the noise in the 4 and 5 kHz bands. | Experiment | PubMed 2026-11-15 |
| C2 | Wallmeier L, Gessele N, Wiegrebe L (2013). Echolocation versus echo suppression in humans. *Proc. R. Soc. B* 280(1769):20131428. doi:10.1098/rspb.2013.1428 | docs/roadmap.md S5 (precedent for echoes generated in real time from the listener's own vocalisations); S2 (the precedence effect, which normally suppresses echoes, is much weaker when the listener produces the sound). | Experiment, sighted adults | PubMed 2026-11-15 |

## D. Simulation methods and their limits

| ID | Citation | Used by, and what we take from it | Kind | Checked |
| --- | --- | --- | --- | --- |
| D1 | Scheibler R, Bezzam E, Dokmanic I (2018). Pyroomacoustics: a Python package for audio room simulations and array processing algorithms. *IEEE ICASSP*, 351-355. doi:10.1109/ICASSP.2018.8461310 | EXP-0001 and docs/quality/quality-gates.md: an independent cross-check for the mirror-reflection part of the engine only. It has no edge diffraction, so it cannot be the reference for echolocation targets (see decision 2). | Software paper | Unchecked (not indexed in PubMed) |
| D3 | Vorlander M (2013). Computer simulations in room acoustics: concepts and uncertainties. *J. Acoust. Soc. Am.* 133(3):1203-1213. doi:10.1121/1.4788978 | docs/quality/quality-gates.md (room gate): predicting reverberation time to within a just-noticeable difference needs absorption data better than measurements provide, so "within one JND of the measured room" is not a realistic pass mark; docs/decisions/0002. | Review | PubMed 2026-11-15 |
| D5 | Brinkmann F, Aspock L, Ackermann D, Lepa S, Vorlander M, Weinzierl S (2019). A round robin on room acoustical simulation and auralization. *J. Acoust. Soc. Am.* 145(4):2746. doi:10.1121/1.5096178 | docs/decisions/0002 (independent support: simulation software fails on early reflections largely because diffraction is missing or insufficient, and the difference from measurement was always audible); docs/quality/quality-gates.md (state of the art against which room gates are set). | Round robin against measurements | PubMed 2026-11-15 |

## H. Edge diffraction (the engine's method)

| ID | Citation | Used by, and what we take from it | Kind | Checked |
| --- | --- | --- | --- | --- |
| H1 | Svensson UP, Fred RI, Vanderkooy J (1999). An analytic secondary source model of edge diffraction impulse responses. *J. Acoust. Soc. Am.* 106(5):2331-2344. | src/soundsight/acoustics/engine.py and docs/acoustics/engine.md: the formulation of first-order edge diffraction the engine implements, exact for a rigid wedge. Its prefactor and sign are also fixed independently by the engine's boundary-continuity test. | Method paper | Unchecked (not indexed in PubMed); citation from memory |
| H2 | Torres RR, Svensson UP, Kleiner M (2001). Computation of edge diffraction for more accurate room acoustics auralization. *J. Acoust. Soc. Am.* 109(2):600-610. doi:10.1121/1.1340647 | docs/acoustics/engine.md: the time-domain method was validated, diffraction is clearly audible even outside shadow zones, and second-order diffraction to receivers outside shadows can often be neglected; EXP-0003 found the exception that matters to us, objects one or two wavelengths around. | Method and listening study | PubMed 2026-11-16 |
| H3 | Asheim A, Svensson UP (2013). An integral equation formulation for the diffraction from convex plates and polyhedra. *J. Acoust. Soc. Am.* 133(6):3681-3691. doi:10.1121/1.4802654 | docs/acoustics/engine.md (next increment): diffraction of all orders from plates and polyhedra, accurate down to zero frequency, with results for a circular disc that agree with reference solutions across the frequency range. | Method paper | PubMed 2026-11-16 |

## E. Standards, formats and datasets

| ID | Citation | Used by, and what we take from it | Kind | Checked |
| --- | --- | --- | --- | --- |
| E1 | ISO 3382-1 and ISO 3382-2: measurement of room acoustic parameters. | docs/quality/quality-gates.md (room gate, when room reverberation is implemented): the parameter set, reported in JND units. These describe rooms for speech and music; they do not measure the early echoes of nearby objects that echolocation uses. | Standard | Unchecked |
| E3 | BRAS, Benchmark for Room Acoustical Simulation: measured impulse responses, geometry and surface data for simple scenes and rooms. Brinkmann F, Aspock L, Ackermann D, Opdam R, Vorlander M, Weinzierl S (2021). A benchmark for room acoustical simulation: concept and database. *Applied Acoustics* 176:107867. | docs/quality/quality-gates.md and docs/acoustics/validation.md (*planned* measured rung): its simple scenes, such as reflection and diffraction at a finite plate, are measurements of the same kind of problem as our canonical ones. Licence and scene list to be confirmed before use. | Dataset | Unchecked; citation from memory |
| E4 | AES69: SOFA, the file format for head-related transfer functions. | docs/roadmap.md S3 (interchange of generic and personal HRTFs). | Standard | Unchecked |
| F1 | Wenzel EM, Arruda M, Kistler DJ, Wightman FL (1993). Localization using nonindividualized head-related transfer functions. *J. Acoust. Soc. Am.* 94(1):111-123. doi:10.1121/1.407089 | docs/roadmap.md S3: a generic HRTF preserves left-right cues for most listeners but increases front-back and up-down confusions, which is the argument for head tracking before personal HRTFs. | Experiment, 16 listeners | PubMed 2026-11-15 |

## Changes made on review of the 2026-11-15 draft

- **Corrected:** BRAS was attributed to PTB; it is from TU Berlin and RWTH Aachen.
- **Corrected:** the claim that training changes the brain was anchored to Thaler, Arnott
  and Goodale (2011), an imaging study of two experts that involved no training. It is
  now anchored to A5.
- **Added:** A5 and D5.
- **Retired, no consumer yet:** A1 (Thaler, Arnott, Goodale 2011, *PLoS ONE*
  6(5):e20162, record confirmed in PubMed); D4 (Siltanen et al. 2007, the room acoustic
  rendering equation, record confirmed in PubMed), to return if radiance transfer is
  considered for late reverberation; E2 (ISO 17497-1), to return with the materials
  database.
- **Retired, cannot be confirmed:** the draft's D2 ("Comparing Open Source Room
  Acoustics Simulation Tools", Forum Acusticum 2025). No author list or identifier was
  available and its specific findings could not be checked. D5 serves the same purpose
  with a confirmed record.
- **Dropped:** the draft's letter grades. Grade A required independent replication,
  which none of the graded entries has; the "Kind" column states what each source is.
- The protocol details the draft attributes to A3 were confirmed against the full text.
