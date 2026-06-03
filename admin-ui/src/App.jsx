import { useState, useEffect } from "react"
import axios from "axios"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts"
import {
  Activity, Key, Users, Zap,
  AlertCircle, Clock, Database, RefreshCw
} from "lucide-react"

const api = axios.create({ baseURL: "/api" })

function StatCard({ icon: Icon, label, value, sub, color = "blue" }) {
  const colors = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    purple: "bg-purple-50 text-purple-600",
    red: "bg-red-50 text-red-600",
    amber: "bg-amber-50 text-amber-600",
  }
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-500 font-medium">{label}</span>
        <div className={`p-2 rounded-lg ${colors[color]}`}>
          <Icon size={16} />
        </div>
      </div>
      <div className="text-2xl font-bold text-gray-800">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  )
}

function Login({ onLogin }) {
  const [email, setEmail] = useState("akshata@nexus.ai")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.post("/auth/login", { email, password })
      localStorage.setItem("token", res.data.access_token)
      api.defaults.headers.common["Authorization"] = `Bearer ${res.data.access_token}`
      onLogin()
    } catch {
      setError("Invalid email or password")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 w-full max-w-sm">
        <div className="flex items-center gap-2 mb-6">
          <Zap className="text-blue-600" size={24} />
          <h1 className="text-xl font-bold text-gray-800">NexusLLM</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">Sign in to the admin dashboard</p>
        <div className="space-y-3">
          <input
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <input
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
          />
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            onClick={submit}
            disabled={loading}
            className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  )
}

function Dashboard() {
  const [stats, setStats] = useState(null)
  const [logs, setLogs] = useState([])
  const [users, setUsers] = useState([])
  const [tab, setTab] = useState("overview")
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = async () => {
    setRefreshing(true)
    try {
      const [s, l, u] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/audit-logs?limit=20"),
        api.get("/admin/users"),
      ])
      setStats(s.data)
      setLogs(l.data)
      setUsers(u.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-gray-400 text-sm">Loading dashboard...</div>
    </div>
  )

  const providerData = stats
    ? Object.entries(stats.by_provider).map(([k, v]) => ({ name: k, requests: v }))
    : []

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="text-blue-600" size={20} />
            <span className="font-bold text-gray-800">NexusLLM</span>
            <span className="text-gray-300 mx-2">|</span>
            <span className="text-sm text-gray-500">Admin Dashboard</span>
          </div>
          <button
            onClick={load}
            disabled={refreshing}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
          >
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
          {["overview", "logs", "users"].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-all ${
                tab === t
                  ? "bg-white text-gray-800 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {tab === "overview" && stats && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <StatCard icon={Activity} label="Requests (24h)" value={stats.total_requests_24h} sub="last 24 hours" color="blue" />
              <StatCard icon={Database} label="Tokens (24h)" value={stats.total_tokens_24h.toLocaleString()} sub="prompt + completion" color="purple" />
              <StatCard icon={Clock} label="Avg Latency" value={`${stats.avg_latency_ms}ms`} sub="per request" color="green" />
              <StatCard icon={AlertCircle} label="Error Rate" value={`${stats.error_rate_pct}%`} sub="last 24 hours" color="red" />
              <StatCard icon={Users} label="Total Users" value={stats.total_users} sub="registered" color="amber" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Provider chart */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Requests by provider</h3>
                {providerData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={providerData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Bar dataKey="requests" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-44 flex items-center justify-center text-sm text-gray-400">
                    No data yet — make some proxy requests
                  </div>
                )}
              </div>

              {/* Model breakdown */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Top models</h3>
                {stats.by_model.length > 0 ? (
                  <div className="space-y-3">
                    {stats.by_model.map((m, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="text-xs text-gray-500 w-40 truncate">{m.model}</div>
                        <div className="flex-1 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{ width: `${(m.requests / stats.by_model[0].requests) * 100}%` }}
                          />
                        </div>
                        <div className="text-xs font-medium text-gray-700 w-6 text-right">
                          {m.requests}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-44 flex items-center justify-center text-sm text-gray-400">
                    No data yet
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {tab === "logs" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">Audit log</h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Every request — metadata only, no prompt content stored
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-3 font-medium">Time</th>
                    <th className="px-4 py-3 font-medium">Provider</th>
                    <th className="px-4 py-3 font-medium">Model</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Latency</th>
                    <th className="px-4 py-3 font-medium">Tokens</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                        No logs yet — make some proxy requests first
                      </td>
                    </tr>
                  ) : logs.map(log => (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-3">
                        {log.provider ? (
                          <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-xs font-medium">
                            {log.provider}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-gray-600 max-w-32 truncate">
                        {log.model || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          log.status_code < 400
                            ? "bg-green-50 text-green-700"
                            : "bg-red-50 text-red-700"
                        }`}>
                          {log.status_code}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{log.latency_ms}ms</td>
                      <td className="px-4 py-3 text-gray-600">
                        {log.prompt_tokens && log.completion_tokens
                          ? log.prompt_tokens + log.completion_tokens
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Users Tab */}
        {tab === "users" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">Users</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Email</th>
                    <th className="px-4 py-3 font-medium">Team</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Active keys</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {users.map(user => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-700">{user.full_name}</td>
                      <td className="px-4 py-3 text-gray-500">{user.email}</td>
                      <td className="px-4 py-3 text-gray-500">{user.team || "—"}</td>
                      <td className="px-4 py-3">
                        <span className="bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full text-xs font-medium">
                          {user.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <Key size={10} className="text-gray-400" />
                          <span className="text-gray-600">{user.active_keys}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          user.is_active
                            ? "bg-green-50 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}>
                          {user.is_active ? "active" : "inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`
      setAuthed(true)
    }
  }, [])

  return authed ? <Dashboard /> : <Login onLogin={() => setAuthed(true)} />
}