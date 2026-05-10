import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { TrendingUp, Users, Euro, CloudLightning } from 'lucide-react';

export default function App() {
  const [data, setData] = useState({ kpis: [], billing: [] });
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const backendUrl = '__API_BASE_URL__';

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/investor-metrics`);
      const json = await res.json();
      if (json.success) {
        setData(json);
        setFetched(true);
      }
    } catch (e) {
      console.error("Error al recuperar métricas: ", e);
      alert("Error conectando con el backend. Verifica la URL.");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-gray-900">AItonomo <span className="text-blue-600">Metrics</span></h1>
        </div>

        {!fetched ? (
          <div className="text-center py-20 text-gray-500">Cargando métricas de rendimiento...</div>
        ) : (
          <>
            {/* Tarjetas de Resumen */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <div className="flex items-center gap-4">
                  <div className="p-4 bg-blue-50 rounded-full text-blue-600"><Users size={28} /></div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Total Usuarios</p>
                    <p className="text-3xl font-bold text-gray-800">{data.kpis.reduce((acc, curr) => acc + curr.nuevos_usuarios, 0)}</p>
                  </div>
                </div>
              </div>
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <div className="flex items-center gap-4">
                  <div className="p-4 bg-green-50 rounded-full text-green-600"><Euro size={28} /></div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Volumen Procesado (GMV)</p>
                    <p className="text-3xl font-bold text-gray-800">
                      {data.kpis.reduce((acc, curr) => acc + curr.gmv_gestionado_eur, 0).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                    </p>
                  </div>
                </div>
              </div>
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <div className="flex items-center gap-4">
                  <div className="p-4 bg-purple-50 rounded-full text-purple-600"><TrendingUp size={28} /></div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Facturas Generadas</p>
                    <p className="text-3xl font-bold text-gray-800">{data.kpis.reduce((acc, curr) => acc + curr.facturas_generadas, 0)}</p>
                  </div>
                </div>
              </div>
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <div className="flex items-center gap-4">
                  <div className="p-4 bg-orange-50 rounded-full text-orange-600"><CloudLightning size={28} /></div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Coste de Infra (Burn)</p>
                    <p className="text-3xl font-bold text-gray-800">
                      {data.billing.reduce((acc, curr) => acc + curr.coste_gcp, 0).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Gráficos */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h2 className="text-xl font-bold mb-6 text-gray-800">Crecimiento de Volumen Gestionado</h2>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.kpis}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="mes" axisLine={false} tickLine={false} />
                      <YAxis axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: 'transparent' }} />
                      <Line type="monotone" dataKey="gmv_gestionado_eur" name="GMV (€)" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h2 className="text-xl font-bold mb-6 text-gray-800">Crecimiento de Tracción (Usuarios)</h2>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.kpis}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="mes" axisLine={false} tickLine={false} />
                      <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip cursor={{ fill: '#f3f4f6' }} />
                      <Bar dataKey="nuevos_usuarios" name="Nuevos Usuarios" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}