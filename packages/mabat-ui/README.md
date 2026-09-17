# mabat-ui

A Streamlit dashboard for [mabat](https://github.com/musondaAlexander/mabat).

```console
pip install mabat-ui             # pulls in mabat, streamlit, pandas
mabat-ui                         # opens http://localhost:8501
mabat-ui --server.port 9000      # any `streamlit run` flag passes through
```

Headline metrics (CPU, RAM, GPU, network) plus one panel per section, refreshing on a
sidebar-selected interval. Sections the host cannot answer show their reason instead of
an empty panel. `--redact` in the sidebar masks identity before you screenshot it.
