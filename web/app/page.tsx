'use client'

import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, Brain } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

async function fetchHealth() {
  const response = await axios.get(`${API_BASE_URL}/health`)
  return response.data
}

async function fetchReport() {
  const response = await axios.get(`${API_BASE_URL}/report`)
  return response.data
}

export default function Dashboard() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ['report'],
    queryFn: fetchReport,
  })

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-2">
        <Activity className="h-6 w-6" />
        <h1 className="text-3xl font-bold">Engineering Radar</h1>
        {health && (
          <span className="ml-auto text-sm text-muted-foreground">
            API Status: {healthLoading ? 'Loading...' : health.status}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* KPIs Panel */}
        <div className="lg:col-span-1">
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="h-5 w-5" />
              <h2 className="text-xl font-semibold">KPIs</h2>
            </div>
            {reportLoading ? (
              <div className="space-y-4">
                <div className="h-4 bg-muted rounded animate-pulse" />
                <div className="h-4 bg-muted rounded animate-pulse" />
                <div className="h-4 bg-muted rounded animate-pulse" />
              </div>
            ) : (
              <div className="space-y-4">
                {/* TODO: Replace with real KPI data */}
                <div>
                  <p className="text-sm text-muted-foreground">Velocity</p>
                  <p className="text-2xl font-bold">TODO</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Cycle Time</p>
                  <p className="text-2xl font-bold">TODO</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Deployment Frequency</p>
                  <p className="text-2xl font-bold">TODO</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Event Stream Panel */}
        <div className="lg:col-span-1">
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-5 w-5" />
              <h2 className="text-xl font-semibold">Recent Activity</h2>
            </div>
            {reportLoading ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12 bg-muted rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {/* TODO: Replace with real event stream */}
                <p className="text-muted-foreground">No recent activity</p>
                <p className="text-sm">Connect GitHub and Linear to see events</p>
              </div>
            )}
          </div>
        </div>

        {/* AI Panel */}
        <div className="lg:col-span-1">
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <Brain className="h-5 w-5" />
              <h2 className="text-xl font-semibold">AI Focus Actions</h2>
            </div>
            {reportLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 bg-muted rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {report?.focus_actions?.map((action: string, index: number) => (
                  <div key={index} className="p-3 bg-secondary rounded-md">
                    <p className="text-sm">{action}</p>
                  </div>
                )) || (
                  <p className="text-muted-foreground">
                    Connect your tools to get AI-powered insights
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
