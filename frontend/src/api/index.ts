import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:8000/api' : '/api',
  timeout: 30000,
})

export interface LayerInfo {
  name: string
  url: string
  width: number
  height: number
}

export interface TaskResponse {
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  message?: string
  layers?: LayerInfo[]
  error?: string
}

export const uploadImage = async (
  file: File,
  numLayers: number = 4,
  prompt: string = ''
): Promise<{ task_id: string }> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('num_layers', numLayers.toString())
  formData.append('prompt', prompt)
  const { data } = await api.post('/upload', formData)
  return data
}

export const getTaskStatus = async (taskId: string): Promise<TaskResponse> => {
  const { data } = await api.get(`/task/${taskId}`)
  return data
}

export const downloadPSD = async (taskId: string) => {
  const baseURL = import.meta.env.DEV ? 'http://localhost:8000' : ''
  const response = await fetch(`${baseURL}/api/download/${taskId}`)
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `layered_${taskId}.psd`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

export const downloadLayerPNG = (url: string, name: string) => {
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}.png`
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
