export default () => {
  return {
    theme: {
      locale: 'en',
      colorPrimary: '#615CED',
      darkMode: true,
      prefix: 'agentscope-runtime-webui',
      leftHeader: {
        logo: '/icons/agent_default_logo.png',
        title: 'Runtime WebUI',
      },
    },
    sender: {
      // @ts-ignore
      attachments: true,
      maxLength: 10000,
      disclaimer:
        'AI can also make mistakes, so please check carefully and use it with caution',
      suggestions: [
        {
          label: 'Draw a picture',
          value: 'draw',
        },
        {
          label: 'Check some knowledge',
          value: 'knowledge',
        },
      ],
    },

    welcome: {
      greeting: 'Hello, how can I help you today?',
      nick: 'Assistant',
      description:
        'I am a helpful assistant that can help you with your questions.',
      avatar:
        '/icons/agent_default_logo.png',

      prompts: [
        {
          value: 'Hello',
        },
        {
          value: 'How are you?',
        },
        {
          value: 'What can you do?',
        },
      ],
    },
    api: {
      baseURL: '',
      token: '',
    },
  };
};
