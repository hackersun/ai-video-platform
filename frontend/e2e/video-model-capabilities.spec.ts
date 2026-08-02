import { expect, test } from '@playwright/test';

import {
  buildVideoReferencePayload,
  videoApiErrorMessage,
  videoModelRequestBinding,
} from '../src/features/video-generation/video-model-capabilities';


test('canonical video selection sends profile version instead of legacy config id', () => {
  expect(videoModelRequestBinding({
    config_id: null,
    model_profile_version_id: 'profile-video-v2',
  })).toEqual({ model_profile_version_id: 'profile-video-v2' });
});


test('legacy video selection keeps legacy model config id', () => {
  expect(videoModelRequestBinding({
    config_id: 'legacy-config-1',
    model_profile_version_id: null,
  })).toEqual({ model_config_id: 'legacy-config-1' });
});


test('manual reference payload follows selected model limits', () => {
  expect(buildVideoReferencePayload(
    { limits: { reference_images: 2, reference_videos: 1, reference_audios: 1 } },
    {
      images: 'https://cdn.example.com/a.png\nhttps://cdn.example.com/b.png',
      videos: 'https://cdn.example.com/clip.mp4',
      audios: 'https://cdn.example.com/voice.wav',
    },
  )).toEqual({
    reference_image_urls: ['https://cdn.example.com/a.png', 'https://cdn.example.com/b.png'],
    reference_video_urls: ['https://cdn.example.com/clip.mp4'],
    reference_audio_urls: ['https://cdn.example.com/voice.wav'],
  });
});


test('manual reference payload reports capacity instead of silently dropping input', () => {
  expect(() => buildVideoReferencePayload(
    { limits: { reference_images: 0, reference_videos: 1, reference_audios: 0 } },
    { images: '', videos: 'https://cdn.example.com/a.mp4\nhttps://cdn.example.com/b.mp4', audios: '' },
  )).toThrow('当前模型最多支持 1 个视频参考');
});


test('video API structured preflight error is readable', () => {
  expect(videoApiErrorMessage({
    detail: { message: '生成预检未通过', issues: [{ message: '角色参考图缺失' }] },
  }, '提交失败')).toBe('生成预检未通过：角色参考图缺失');
});
