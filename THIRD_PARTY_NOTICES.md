# TotalSegmentator

Optional backend: TotalSegmentator 2.18.0 by Jakob Wasserthal and contributors.
The standard CT `total` task and its v2.0.0-weights checkpoints are listed under
Apache-2.0 in the [pinned release README](https://github.com/wasserth/TotalSegmentator/blob/v2.18.0/README.md).
The label catalog in `anatomy_labels.json` is extracted without semantic changes
from that release's `totalsegmentator/map_to_binary.py`. Model manifests add locally
measured SHA-256 integrity pins. The complete upstream Apache-2.0 license is in
`licenses/TotalSegmentator-Apache-2.0.txt`. No separate NOTICE file is supplied
in the installed TotalSegmentator distribution. Our adapter code remains MIT.

Only standard CT total checkpoints 291-295 and 297 are used. Specialized
heart-chamber/coronary and other restricted tasks are not included. Model binaries
and dependencies are downloaded separately into an ignored local worker/cache;
they are not bundled into this repository. Their installed distributions retain
their own licenses, including nnU-Net (Apache-2.0), PyTorch (BSD-style), NumPy
(BSD-3-Clause), nibabel (MIT), and SimpleITK (Apache-2.0). Redistributors of a worker
environment must retain those distributions' full license/notice files.

Requested scientific citations (separate from license requirements):

- Wasserthal et al. TotalSegmentator: Robust Segmentation of 104 Anatomic
  Structures in CT Images. Radiology: Artificial Intelligence (2023).
  https://doi.org/10.1148/ryai.230024
- Isensee et al. nnU-Net: a self-configuring method for deep learning-based
  biomedical image segmentation. Nature Methods 18, 203-211 (2021).
  https://doi.org/10.1038/s41592-020-01008-z

# Lucide Icons

The viewer bundle includes three icons and the element creation helper from
Lucide 0.468.0.

ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of
Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
