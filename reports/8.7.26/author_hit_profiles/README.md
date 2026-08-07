# API-based author hit profiles

Exploratory profiles for Michael Jensen, Manuel Arellano, and Robert Solow,
built from the live OpenAlex API without the external SSD. Start with
`author_hit_profiles.csv` for headline results, `author_hit_event_time.csv` for
tidy event series, and `author_hit_profiles.md` for the figures.

The script clusters obvious versions using DOI or highly similar titles within
one publication year. It does not solve OpenAlex author-identity errors. All
pre/post differences are descriptive and must not be interpreted causally.
