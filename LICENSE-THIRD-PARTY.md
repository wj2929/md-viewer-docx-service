# Third Party Licenses

## Fonts

This repository does not include proprietary Microsoft or Founder font files by default.

The `fonts/` directory may be populated by the user before building a private image:

- Microsoft YaHei
- SimSun
- SimHei
- FangSong
- KaiTi
- Founder XiaoBiaoSong

Only copy these files when you have the legal right to use and redistribute them in your environment.

The Docker images install Debian `fonts-noto-cjk` from the base distribution repositories. Noto CJK fonts are distributed under the SIL Open Font License.

## Runtime Dependencies

Python dependencies are listed in `requirements.txt` and `requirements-full.txt`. Their licenses should be reviewed before redistribution in regulated environments.
