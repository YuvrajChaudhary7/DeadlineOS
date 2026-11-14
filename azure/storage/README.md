# Azure Blob Storage design (DP-900)

Store assignment binaries in a private container with public access disabled. The API authenticates a user and checks enrollment/deadline rules before writing a random object key; SQL stores only key and metadata. Use managed identity, encryption, TLS, size/type allowlists, malware scanning, retention policy and short-lived user-delegation SAS URLs for downloads. Never keep long-lived account keys in source. This is a design note, not a provisioned resource.
