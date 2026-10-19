from modelscope.hub.snapshot_download import snapshot_download

snapshot_download(
    'Qwen/Qwen2.5-7B-Instruct',
    cache_dir='./Qwen2.5-7B-Instruct'
)