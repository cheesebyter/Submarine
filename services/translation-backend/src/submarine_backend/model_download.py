from huggingface_hub import snapshot_download

from submarine_backend.config import get_settings


def main() -> None:
    settings = get_settings()
    destination = settings.model_path.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=settings.model_name,
        local_dir=destination,
    )
    if not (destination / "model.bin").is_file():
        raise RuntimeError("Model download completed without model.bin")
    print(f"Whisper model is ready in {destination}")


if __name__ == "__main__":
    main()
