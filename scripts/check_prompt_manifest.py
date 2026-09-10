"""Fail when a production prompt version or content hash is stale."""

from clutch.prompts.manifest import load_and_validate_prompt_manifest


def main() -> None:
    manifest = load_and_validate_prompt_manifest()
    print(f"Validated {len(manifest.prompts)} versioned production prompts.")


if __name__ == "__main__":
    main()
