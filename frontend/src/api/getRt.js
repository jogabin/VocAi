import http from './http'

export async function fetchHello() {
  const { data } = await http.get('/wellcom')
  return data // { message: "hello world" }
}