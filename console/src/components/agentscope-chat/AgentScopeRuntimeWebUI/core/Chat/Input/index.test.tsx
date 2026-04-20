import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UploadFile } from "antd";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Input from "./index";
import { RUNTIME_INPUT_SET_CONTENT_EVENT } from "../hooks/followUpSubmit";

const attachmentState = {
  currentFileList: [] as UploadFile[],
  getFileList: vi.fn<() => UploadFile[]>(),
  setFileList: vi.fn((next: UploadFile[]) => {
    attachmentState.currentFileList = next;
  }),
};

vi.mock("@/components/agentscope-chat", () => ({
  ChatInput: (props: {
    value?: string;
    onChange?: (value: string) => void;
    onSubmit?: () => void;
  }) => (
    <div>
      <input
        data-testid="chat-input"
        value={props.value || ""}
        onChange={(event) => props.onChange?.(event.target.value)}
      />
      <button type="button" onClick={() => props.onSubmit?.()}>
        submit
      </button>
    </div>
  ),
  Disclaimer: () => null,
  useProviderContext: () => ({
    getPrefixCls: (prefix: string) => prefix,
  }),
}));

vi.mock("../../Context/ChatAnywhereOptionsContext", () => ({
  useChatAnywhereOptions: (selector: (value: { sender: object }) => unknown) =>
    selector({ sender: {} }),
}));

vi.mock("../../Context/ChatAnywhereInputContext", () => ({
  useChatAnywhereInput: (
    selector: (value: { disabled: boolean; loading: boolean }) => unknown,
  ) => selector({ disabled: false, loading: false }),
}));

vi.mock("./useAttachments", () => ({
  default: () => ({
    getFileList: attachmentState.getFileList,
    setFileList: attachmentState.setFileList,
    handlePasteFile: undefined,
    uploadIconButton: null,
    uploadFileListHeader: null,
  }),
}));

describe("Chat Input restore flow", () => {
  beforeEach(() => {
    attachmentState.currentFileList = [];
    attachmentState.getFileList.mockImplementation(
      () => attachmentState.currentFileList,
    );
    attachmentState.getFileList.mockClear();
    attachmentState.setFileList.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it("restores attachments and biz_params when follow-up auto-submit fails", async () => {
    const onSubmit = vi.fn();
    const restoredFiles = [
      {
        uid: "restored-file",
        name: "demo.txt",
        response: { url: "/demo.txt" },
      },
    ] as UploadFile[];
    const biz_params = {
      user_prompt_params: {
        source: "follow-up",
      },
    };

    render(<Input onCancel={vi.fn()} onSubmit={onSubmit} />);

    document.dispatchEvent(
      new CustomEvent(RUNTIME_INPUT_SET_CONTENT_EVENT, {
        detail: {
          content: "recover me",
          fileList: restoredFiles,
          biz_params,
        },
      }),
    );

    await waitFor(() => {
      expect(
        (screen.getByTestId("chat-input") as HTMLInputElement).value,
      ).toBe("recover me");
    });
    expect(attachmentState.setFileList).toHaveBeenCalledWith(restoredFiles);

    fireEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        query: "recover me",
        fileList: restoredFiles,
        biz_params,
      });
    });
    expect(attachmentState.setFileList).toHaveBeenLastCalledWith([]);
  });

  it("clears restored biz_params when input content is replaced programmatically", async () => {
    const onSubmit = vi.fn();
    const biz_params = {
      user_prompt_params: {
        source: "follow-up",
      },
    };

    render(<Input onCancel={vi.fn()} onSubmit={onSubmit} />);

    document.dispatchEvent(
      new CustomEvent(RUNTIME_INPUT_SET_CONTENT_EVENT, {
        detail: {
          content: "recover me",
          biz_params,
        },
      }),
    );

    document.dispatchEvent(
      new CustomEvent(RUNTIME_INPUT_SET_CONTENT_EVENT, {
        detail: {
          content: "normal prompt",
        },
      }),
    );

    await waitFor(() => {
      expect(
        (screen.getByTestId("chat-input") as HTMLInputElement).value,
      ).toBe("normal prompt");
    });

    fireEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        query: "normal prompt",
        fileList: [],
        biz_params: undefined,
      });
    });
  });

  it("clears restored biz_params after the user edits the recovered content", async () => {
    const onSubmit = vi.fn();
    const biz_params = {
      user_prompt_params: {
        source: "follow-up",
      },
    };

    render(<Input onCancel={vi.fn()} onSubmit={onSubmit} />);

    document.dispatchEvent(
      new CustomEvent(RUNTIME_INPUT_SET_CONTENT_EVENT, {
        detail: {
          content: "recover me",
          biz_params,
        },
      }),
    );

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "another question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        query: "another question",
        fileList: [],
        biz_params: undefined,
      });
    });
  });
});
