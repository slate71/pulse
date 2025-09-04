export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">Pulse</h1>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  )
}