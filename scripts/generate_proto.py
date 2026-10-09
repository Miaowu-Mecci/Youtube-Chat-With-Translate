"""Regenerate the official YouTube gRPC bindings from the vendored definition."""
import pathlib

import grpc_tools
from grpc_tools import protoc

root = pathlib.Path(__file__).resolve().parent.parent
proto = root / "app" / "proto"
includes = pathlib.Path(grpc_tools.__file__).parent / "_proto"
exit_code = protoc.main([
    "protoc", f"-I{proto}", f"-I{includes}", f"--python_out={proto}", f"--grpc_python_out={proto}",
    str(proto / "stream_list.proto"),
])
if exit_code:
    raise SystemExit(exit_code)
generated = proto / "stream_list_pb2_grpc.py"
generated.write_text(generated.read_text().replace(
    "import stream_list_pb2 as stream__list__pb2", "from . import stream_list_pb2 as stream__list__pb2"
))
