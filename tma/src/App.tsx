import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Reviews from './pages/Reviews'
import Inventory from './pages/Inventory'
import './App.css'

function App() {
  const [isDark, setIsDark] = useState(true)

  useEffect(() => {
    // Apply dark mode class to document
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDark])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
        <nav className="sticky top-0 z-10 bg-gray-100 dark:bg-gray-800 border-b border-gray-300 dark:border-gray-700 shadow-sm">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between py-3">
              <div className="flex space-x-4">
                <NavLink
                  to="/"
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-sm font-medium ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`
                  }
                >
                  📊 Dashboard
                </NavLink>
                <NavLink
                  to="/reviews"
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-sm font-medium ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`
                  }
                >
                  ⭐ Reviews
                </NavLink>
                <NavLink
                  to="/inventory"
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-sm font-medium ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`
                  }
                >
                  📦 Inventory
                </NavLink>
              </div>
              <button
                onClick={() => setIsDark(!isDark)}
                className="px-3 py-2 rounded-md text-sm font-medium bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600"
                title="Toggle dark mode"
              >
                {isDark ? '☀️' : '🌙'}
              </button>
            </div>
          </div>
        </nav>

        <main className="container mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="/inventory" element={<Inventory />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
