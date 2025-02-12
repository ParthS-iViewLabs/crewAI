import warnings
from abc import ABC, abstractmethod
from inspect import signature
from typing import Any, Callable, Optional, Type, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PydanticDeprecatedSince20,
    create_model,
    validator,
)
from pydantic import BaseModel as PydanticBaseModel

from crewai.tools.structured_tool import CrewStructuredTool

# Ignore all "PydanticDeprecatedSince20" warnings globally
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)


class BaseTool(BaseModel, ABC):
    class _ArgsSchemaPlaceholder(PydanticBaseModel):
        pass

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        from_attributes=True,  # Allow conversion from ORM objects
    )

    name: str
    """The unique name of the tool that clearly communicates its purpose."""
    description: str
    """Used to tell the model how/when/why to use the tool."""
    args_schema: Type[PydanticBaseModel] = Field(default_factory=_ArgsSchemaPlaceholder)
    """The schema for the arguments that the tool accepts."""
    description_updated: bool = False
    """Flag to check if the description has been updated."""
    cache_function: Callable = lambda _args=None, _result=None: True
    """Function that will be used to determine if the tool should be cached, should return a boolean. If None, the tool will be cached."""
    result_as_answer: bool = False
    """Flag to check if the tool should be the final agent answer."""

    @validator("args_schema", always=True, pre=True)
    def _default_args_schema(
        cls, v: Type[PydanticBaseModel]
    ) -> Type[PydanticBaseModel]:
        if not isinstance(v, cls._ArgsSchemaPlaceholder):
            return v

        return type(
            f"{cls.__name__}Schema",
            (PydanticBaseModel,),
            {
                "__annotations__": {
                    k: v for k, v in cls._run.__annotations__.items() if k != "return"
                },
            },
        )

    def model_post_init(self, __context: Any) -> None:
        self._generate_description()

        super().model_post_init(__context)

    def run(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        print(f"Using Tool: {self.name}")
        return self._run(*args, **kwargs)

    @abstractmethod
    def _run(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Here goes the actual implementation of the tool."""

    def to_structured_tool(self) -> CrewStructuredTool:
        """Convert this tool to a CrewStructuredTool instance."""
        self._set_args_schema()
        return CrewStructuredTool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            func=self._run,
            result_as_answer=self.result_as_answer,
        )

    @classmethod
    def from_langchain(cls, tool: Any) -> "BaseTool":
        print("CREATING TOOL FROM LANGCHAIN")
        """Create a Tool instance from a CrewStructuredTool.

        This method takes a CrewStructuredTool object and converts it into a
        Tool instance. It ensures that the provided tool has a callable 'func'
        attribute and infers the argument schema if not explicitly provided.
        """
        if not hasattr(tool, "func") or not callable(tool.func):
            raise ValueError("The provided tool must have a callable 'func' attribute.")

        args_schema = getattr(tool, "args_schema", None)

        if args_schema is None:
            # Infer args_schema from the function signature if not provided
            func_signature = signature(tool.func)
            annotations = func_signature.parameters
            args_fields = {}
            for name, param in annotations.items():
                if name != "self":
                    param_annotation = (
                        param.annotation if param.annotation != param.empty else Any
                    )
                    field_info = Field(
                        default=...,
                        description="",
                    )
                    args_fields[name] = (param_annotation, field_info)
            if args_fields:
                args_schema = create_model(f"{tool.name}Input", **args_fields)
            else:
                # Create a default schema with no fields if no parameters are found
                args_schema = create_model(
                    f"{tool.name}Input", __base__=PydanticBaseModel
                )

        return cls(
            name=getattr(tool, "name", "Unnamed Tool"),
            description=getattr(tool, "description", ""),
            func=tool.func,
            args_schema=args_schema,
        )

    def _set_args_schema(self):
        if self.args_schema is None:
            class_name = f"{self.__class__.__name__}Schema"
            self.args_schema = type(
                class_name,
                (PydanticBaseModel,),
                {
                    "__annotations__": {
                        k: v
                        for k, v in self._run.__annotations__.items()
                        if k != "return"
                    },
                },
            )

    def _generate_description(self):
        args_schema = {
            name: {
                "description": field.description,
                "type": BaseTool._get_arg_annotations(field.annotation),
            }
            for name, field in self.args_schema.model_fields.items()
        }

        self.description = f"Tool Name: {self.name}\nTool Arguments: {args_schema}\nTool Description: {self.description}"

    @staticmethod
    def _get_arg_annotations(annotation: type[Any] | None) -> str:
        if annotation is None:
            return "None"

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is None:
            return (
                annotation.__name__
                if hasattr(annotation, "__name__")
                else str(annotation)
            )

        if args:
            args_str = ", ".join(BaseTool._get_arg_annotations(arg) for arg in args)
            return f"{origin.__name__}[{args_str}]"

        return origin.__name__

    def to_langchain(self) -> Any:
        """
        Convert this CrewAI Tool instance into a LangChain-compatible tool.
        Returns a concrete subclass of LangChain's BaseTool.
        """
        try:
            from langchain_core.tools import Tool as LC_Tool
        except ImportError as e:
            raise ImportError(
                "LangChain library not found. Please run `uv add langchain` to add LangChain support."
            ) from e

        # Capture the function in a local variable to avoid referencing None.
        tool_func = self.func

        class ConcreteLangChainTool(LC_Tool):
            def _run(self, *args, **kwargs):
                return tool_func(*args, **kwargs)

        # Do not pass callback_manager; let LC_Tool use its default.
        print("Creating concrete langchain tool")
        return ConcreteLangChainTool(
            name=self.name,
            description=self.description,
            func=tool_func,
            args_schema=self.args_schema,
        )

    @property
    def get(self) -> Callable[[str, Any], Any]:
        # Returns a callable that looks up attributes on the instance.
        return lambda key, default=None: getattr(self, key, default)


class Tool(BaseTool):
    """Tool implementation that requires a function."""

    func: Callable
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        from_attributes=True,
    )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    @classmethod
    def from_langchain(cls, tool: Any) -> "Tool":
        """Convert a LangChain tool to a CrewAI Tool."""
        # Handle missing args_schema
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            # Create default args schema
            args_schema = create_model(f"{tool.name}Input", __base__=PydanticBaseModel)
        tool_dict = {
            "name": tool.name,
            "description": tool.description,
            "func": tool._run,  # LangChain tools use _run
            "args_schema": args_schema,
        }
        # Create and validate a new instance directly from the dictionary
        return cls.model_validate(tool_dict)

    def to_langchain(self) -> Any:
        """Convert to LangChain tool with proper get method."""
        try:
            from langchain_core.tools import Tool as LC_Tool
        except ImportError:
            raise ImportError("langchain_core is not installed")

        LC_Tool(
            name=self.name,
            description=self.description,
            func=self.func,
            args_schema=self.args_schema,
        )

        # # Create subclass with get method
        # class PatchedTool(LC_Tool):
        #     def get(self, key: str, default: Any = None) -> Any:
        #         return getattr(self, key, default)

        # return PatchedTool(
        #     name=self.name,
        #     description=self.description,
        #     func=self.func,
        #     args_schema=self.args_schema,
        #     callback_manager=None,
        # )


def to_langchain(
    tools: list[BaseTool | CrewStructuredTool],
) -> list[CrewStructuredTool]:
    return [t.to_structured_tool() if isinstance(t, BaseTool) else t for t in tools]


def tool(*args):
    """
    Decorator to create a tool from a function.
    """

    def _make_with_name(tool_name: str) -> Callable:
        def _make_tool(f: Callable) -> BaseTool:
            if f.__doc__ is None:
                raise ValueError("Function must have a docstring")
            if f.__annotations__ is None:
                raise ValueError("Function must have type annotations")

            class_name = "".join(tool_name.split()).title()
            args_schema = type(
                class_name,
                (PydanticBaseModel,),
                {
                    "__annotations__": {
                        k: v for k, v in f.__annotations__.items() if k != "return"
                    },
                },
            )

            return Tool(
                name=tool_name,
                description=f.__doc__,
                func=f,
                args_schema=args_schema,
            )

        return _make_tool

    if len(args) == 1 and callable(args[0]):
        return _make_with_name(args[0].__name__)(args[0])
    if len(args) == 1 and isinstance(args[0], str):
        return _make_with_name(args[0])
    raise ValueError("Invalid arguments")
