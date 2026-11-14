# The 2016 demonstrator

Notes from a review of github.com/SoundSight/SoundSight (commits of 26-27 May 2016),
kept so that the design ideas survive the code.

## What it did

A first-person 3D scene with real-time sound propagation (GSound: ray-traced specular
reflections to depth 4, edge diffraction, transmission and a statistical reverb tail,
in four frequency bands split at 250 Hz, 1 kHz and 4 kHz). The echolocation features
added to the GSound example application were:

- holding a key emits a "tongue click" from a directional source 2 cm in front of the
  listener;
- two keys switch every surface between brick-like and plywood-like absorption;
- listener trajectories can be recorded and replayed, so that a walk through a scene is
  identical every time, a basis for standardised exercises;
- five scenes: a simple room, three outdoor scenes and the Sibenik cathedral model.

## Limits identified

- Output went to a stereo loudspeaker layout, not through head-related transfer
  functions: left/right cues only, no elevation, front/back or externalisation.
- Four frequency bands put nearly all of a click's energy in one band.
- The demo emitted a generic burst, not the high-quality click recorded at 192 kHz.
- The last build log shows an attempt to add live microphone input by editing GSound's
  device headers; this cannot work with a closed binary, and the build failed.
- The repository's open issues list the next steps that were never taken: remove the
  sound-engine dependency, integrate a 3D environment editor, support live microphone
  input.

## The click recording

`clickrecord.wav` (192 kHz, 24-bit, stereo, 10.9 s) holds nine clicks at a steady
interval of about 1.3 s, with a noise floor near -82 dBFS. SoundSight's analysis finds
a median duration of about 2.2 ms and a median peak frequency of about 2.75 kHz, in line
with published descriptions of expert clicks. Some clicks have two spectral peaks of
similar height, so their individual peak frequency varies. The legacy regression test
pins these results.
