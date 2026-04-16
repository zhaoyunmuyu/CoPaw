## ADDED Requirements

### Requirement: 拖拽文件上传覆盖层

在聊天区域拖入文件时，显示上传提示覆盖层。

#### Scenario: 拖入文件显示覆盖层
- **WHEN** 用户将文件从系统文件管理器拖入聊天消息区域
- **THEN** 显示拖拽上传提示卡片（800px 宽、圆角 12、浅蓝背景 #F1F6FF），包含上传图标、"点击或拖放文件到该区域" 文字、格式说明"支持pdf，ppt，doc，excel，png，jpg等格式"、右上角关闭按钮

#### Scenario: 拖出文件隐藏覆盖层
- **WHEN** 用户将文件拖出聊天区域或按 ESC 键
- **THEN** 覆盖层消失，恢复正常聊天界面

#### Scenario: 点击关闭按钮隐藏覆盖层
- **WHEN** 用户点击覆盖层右上角的关闭按钮
- **THEN** 覆盖层消失

### Requirement: 拖拽释放上传文件

#### Scenario: 释放文件触发上传
- **WHEN** 用户在覆盖层显示状态下释放文件到聊天区域
- **THEN** 覆盖层关闭，文件通过现有的 handleFileUpload 流程上传，上传后的文件作为附件添加到输入框

#### Scenario: 多文件拖拽
- **WHEN** 用户同时拖拽多个文件释放
- **THEN** 每个文件依次走 handleFileUpload 流程上传

### Requirement: 欢迎页附件按钮可点击上传

#### Scenario: 点击附件按钮选择文件
- **WHEN** 用户在欢迎页输入框点击附件图标按钮
- **THEN** 触发系统文件选择对话框，选择文件后走 handleFileUpload 上传流程
