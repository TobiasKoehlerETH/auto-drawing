# Fixture Corpus Plan

The OSS drawing pipeline should keep a fixture corpus that covers:

- simple prismatic STEP parts
- turned/revolved geometry
- filleted geometry
- hole patterns
- thin-walled section candidates
- assemblies with repeated components
- AP242 PMI/GD&T metadata cases
- broken or partially valid STEP files

The first repo-backed fixtures should focus on:

1. `fixtures/step/simple-block.step`
2. `fixtures/step/hole-pattern.step`
3. `fixtures/step/invalid-missing-header.step`

Each fixture should eventually have:

- canonical model JSON golden
- preview SVG golden
- final SVG golden
- HTML export golden
- optional PDF golden when Puppeteer export is available
