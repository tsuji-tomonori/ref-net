"""FastAPIルーター関数の戻り値型をチェックするAST解析ツール."""

import ast
import sys
from pathlib import Path


class FastAPIReturnTypeChecker(ast.NodeVisitor):
    """FastAPIルーター関数の戻り値型をチェックするASTビジター."""

    def __init__(self) -> None:
        """チェッカーを初期化."""
        self.errors: list[str] = []
        self.current_file = ""

    def check_file(self, file_path: Path) -> list[str]:
        """ファイルをチェックしてエラーリストを返す."""
        self.current_file = str(file_path)
        self.errors = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            self.visit(tree)
        except SyntaxError as e:
            self.errors.append(f"{self.current_file}:{e.lineno}: SyntaxError: {e.msg}")
        except Exception as e:
            self.errors.append(f"{self.current_file}: Error reading file: {e}")

        return self.errors

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数定義をチェック."""
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """非同期関数定義をチェック."""
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """関数（同期・非同期）の戻り値型をチェック."""
        # FastAPIデコレータがあるかチェック
        if not self._has_fastapi_decorator(node):
            return

        # 戻り値型注釈をチェック
        if node.returns is None:
            self.errors.append(
                f"{self.current_file}:{node.lineno}: "
                f"FastAPIルーター関数 '{node.name}' の戻り値に型注釈を指定してください"
                f"（pydantic.BaseModel のサブクラス）"
            )
        elif not self._is_pydantic_model_annotation(node.returns):
            return_type = ast.unparse(node.returns)
            self.errors.append(
                f"{self.current_file}:{node.lineno}: "
                f"FastAPIルーター関数 '{node.name}' の戻り値型 '{return_type}' は "
                f"pydantic.BaseModel のサブクラスではありません"
            )

    def _has_fastapi_decorator(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """FastAPIのルーターデコレータがあるかチェック."""
        for decorator in node.decorator_list:
            if self._is_fastapi_decorator(decorator):
                return True
        return False

    def _is_fastapi_decorator(self, decorator: ast.expr) -> bool:
        """デコレータがFastAPIのルーターメソッドかチェック."""
        if isinstance(decorator, ast.Call):
            # @router.get() や @app.post() の形式
            if isinstance(decorator.func, ast.Attribute):
                if isinstance(decorator.func.value, ast.Name):
                    # router.get, app.post など
                    obj_name = decorator.func.value.id
                    method_name = decorator.func.attr
                    if obj_name in {"router", "app"} and method_name in {
                        "get", "post", "put", "delete", "patch", "options", "head"
                    }:
                        return True
        return False

    def _is_pydantic_model_annotation(self, annotation: ast.expr) -> bool:
        """型注釈がPydanticモデルかチェック（名前ベース）."""
        annotation_str = ast.unparse(annotation)

        # Anyは明示的に禁止
        if "Any" in annotation_str:
            return False

        # Pydanticモデルの一般的な命名パターンをチェック
        # Model, Response, Request, Schema で終わる名前
        pydantic_patterns = ["Model", "Response", "Request", "Schema"]

        # list[SomeModel] や Optional[SomeModel] の場合も考慮
        for pattern in pydantic_patterns:
            if pattern in annotation_str:
                return True

        # BaseModel の直接的な言及
        if "BaseModel" in annotation_str:
            return True

        return False


def check_file(file_path: Path) -> list[str]:
    """単一ファイルをチェック."""
    checker = FastAPIReturnTypeChecker()
    return checker.check_file(file_path)


def check_directory(directory: Path) -> list[str]:
    """ディレクトリ内のPythonファイルを再帰的にチェック."""
    all_errors = []
    for py_file in directory.rglob("*.py"):
        errors = check_file(py_file)
        all_errors.extend(errors)
    return all_errors


def main() -> None:
    """メイン関数."""
    if len(sys.argv) != 2:
        print("Usage: python -m refnet_api.fastapi_checker <file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"Error: {path} does not exist")
        sys.exit(1)

    if path.is_file():
        errors = check_file(path)
    else:
        errors = check_directory(path)

    if errors:
        for error in errors:
            print(error)
        sys.exit(1)
    else:
        print("No FastAPI return type errors found.")


if __name__ == "__main__":
    main()
