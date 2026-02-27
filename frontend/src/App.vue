<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
    <div class="max-w-6xl mx-auto">
      <header class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-800 mb-2">🎨 图片分层工具</h1>
        <p class="text-gray-600">AI 自动分层，一键生成 PSD</p>
      </header>

      <!-- 状态一：待上传 -->
      <div v-if="state === 'idle'" class="bg-white rounded-2xl shadow-xl p-12">
        <!-- 配置区域 -->
        <div class="mb-8 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">分层数量</label>
            <input
              v-model.number="numLayers"
              type="number"
              min="2"
              max="10"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">提示词（可选）</label>
            <input
              v-model="prompt"
              type="text"
              placeholder="例如：分离前景和背景"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
        </div>

        <!-- 上传区域 -->
        <div
          @drop.prevent="handleDrop"
          @dragover.prevent
          @click="triggerFileInput"
          class="border-4 border-dashed border-gray-300 rounded-xl p-16 text-center cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition"
        >
          <div class="text-6xl mb-4">📁</div>
          <p class="text-xl text-gray-700 mb-2">拖拽图片到这里 / 点击选择</p>
          <p class="text-sm text-gray-500">支持 PNG、JPG，最大 10MB</p>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/jpg"
          @change="handleFileSelect"
          class="hidden"
        />
        <p v-if="error" class="text-red-500 text-center mt-4">{{ error }}</p>
      </div>

      <!-- 状态二：处理中 -->
      <div v-else-if="state === 'processing'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h3 class="text-lg font-semibold mb-4">原图预览</h3>
            <img :src="previewUrl" class="w-full rounded-lg shadow" />
          </div>
          <div class="flex flex-col justify-center items-center">
            <div class="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 mb-4"></div>
            <p class="text-xl font-semibold text-gray-700">AI 分层中...</p>
            <p class="text-sm text-gray-500 mt-2">预计 30 秒</p>
          </div>
        </div>
      </div>

      <!-- 状态三：已完成 -->
      <div v-else-if="state === 'completed'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h3 class="text-lg font-semibold mb-4">原图</h3>
            <img :src="previewUrl" class="w-full rounded-lg shadow" />
          </div>
          <div>
            <h3 class="text-lg font-semibold mb-4">分层结果 ({{ layers.length }} 层)</h3>
            <div class="grid grid-cols-2 gap-4 mb-6">
              <div
                v-for="(layer, i) in layers"
                :key="i"
                class="relative group"
              >
                <div class="checkerboard rounded-lg overflow-hidden cursor-pointer" @click="viewLayer(layer)">
                  <img :src="layer.url" class="w-full" />
                </div>
                <p class="text-xs text-center mt-1 text-gray-600">{{ layer.name }}</p>
                <button
                  @click="downloadLayer(layer)"
                  class="absolute top-2 right-2 bg-white bg-opacity-90 hover:bg-opacity-100 text-gray-700 p-2 rounded-lg shadow opacity-0 group-hover:opacity-100 transition"
                  title="下载此图层"
                >
                  ⬇️
                </button>
              </div>
            </div>
            <div class="flex gap-4">
              <button
                @click="downloadPSDFile"
                class="flex-1 bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition"
              >
                下载 PSD
              </button>
              <button
                @click="reset"
                class="flex-1 bg-gray-200 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-300 transition"
              >
                重新上传
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 状态四：失败 -->
      <div v-else-if="state === 'failed'" class="bg-white rounded-2xl shadow-xl p-12 text-center">
        <div class="text-6xl mb-4">❌</div>
        <p class="text-xl text-red-600 mb-4">{{ error }}</p>
        <button
          @click="reset"
          class="bg-indigo-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition"
        >
          重试
        </button>
      </div>
    </div>

    <!-- 图层放大预览弹窗 -->
    <div
      v-if="viewingLayer"
      @click="viewingLayer = null"
      class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-8"
    >
      <div class="max-w-4xl max-h-full">
        <div class="checkerboard rounded-lg overflow-hidden">
          <img :src="viewingLayer.url" class="max-w-full max-h-[80vh]" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { uploadImage, getTaskStatus, downloadPSD, downloadLayerPNG, type LayerInfo } from './api'

type State = 'idle' | 'processing' | 'completed' | 'failed'

const state = ref<State>('idle')
const error = ref('')
const previewUrl = ref('')
const taskId = ref('')
const layers = ref<LayerInfo[]>([])
const viewingLayer = ref<LayerInfo | null>(null)
const fileInput = ref<HTMLInputElement>()

// 配置参数
const numLayers = ref(4)
const prompt = ref('')

let pollTimer: number | null = null

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) processFile(file)
}

const handleDrop = (e: DragEvent) => {
  const file = e.dataTransfer?.files[0]
  if (file) processFile(file)
}

const processFile = async (file: File) => {
  error.value = ''

  // 校验
  if (!['image/png', 'image/jpeg', 'image/jpg'].includes(file.type)) {
    error.value = '仅支持 PNG 和 JPG 格式'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    error.value = '文件大小不能超过 10MB'
    return
  }

  // 预览
  previewUrl.value = URL.createObjectURL(file)
  state.value = 'processing'

  try {
    const { task_id } = await uploadImage(file, numLayers.value, prompt.value)
    taskId.value = task_id
    startPolling()
  } catch (err: any) {
    state.value = 'failed'
    error.value = err.response?.data?.detail || '上传失败'
  }
}

const startPolling = () => {
  pollTimer = window.setInterval(async () => {
    try {
      const result = await getTaskStatus(taskId.value)
      if (result.status === 'COMPLETED') {
        stopPolling()
        layers.value = result.layers || []
        state.value = 'completed'
      } else if (result.status === 'FAILED') {
        stopPolling()
        state.value = 'failed'
        error.value = result.error || '处理失败'
      }
    } catch (err) {
      console.error('轮询失败:', err)
    }
  }, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const downloadPSDFile = async () => {
  await downloadPSD(taskId.value)
}

const downloadLayer = (layer: LayerInfo) => {
  downloadLayerPNG(layer.url, layer.name)
}

const reset = () => {
  stopPolling()
  state.value = 'idle'
  error.value = ''
  previewUrl.value = ''
  taskId.value = ''
  layers.value = []
  numLayers.value = 4
  prompt.value = ''
}

const viewLayer = (layer: LayerInfo) => {
  viewingLayer.value = layer
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.checkerboard {
  background-image: linear-gradient(45deg, #ccc 25%, transparent 25%),
    linear-gradient(-45deg, #ccc 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #ccc 75%),
    linear-gradient(-45deg, transparent 75%, #ccc 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
</style>
