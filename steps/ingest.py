import yaml
from sklearn.datasets import fetch_california_housing


def ingest():
    with open("params.yaml") as f:
        params = yaml.safe_load(f)

    raw_path = params["data"]["raw_path"]

    dataset = fetch_california_housing(as_frame=True)
    df = dataset.frame

    df.to_csv(raw_path, index=False)
    print(f"Data saved to {raw_path} — {df.shape[0]} rows, {df.shape[1]} columns")


if __name__ == "__main__":
    ingest()