"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { tokenManager } from '@/lib/token-manager';

interface SearchResult {
  document: {
    id: string;
    content: string;
    metadata: Record<string, any>;
  };
  score: number;
  debug_info?: Record<string, any>;
}

interface DebugInfo {
  query_embedding?: number[];
  embedding_dimension?: number;
  score_stats?: {
    min: number;
    max: number;
    avg: number;
    stddev: number;
  };
  collection_stats?: {
    total_documents: number;
    total_chunks: number;
    languages: string[];
  };
}

export default function RAGDemoPage() {
  const { user, loading } = useAuth();
  const [query, setQuery] = useState('are sd card backups encrypted?');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [debugInfo, setDebugInfo] = useState<DebugInfo>({});
  const [searchTime, setSearchTime] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Configuration state
  const [config, setConfig] = useState({
    max_results: 10,
    score_threshold: 0.3,
    collection_name: '',
    chunk_size: 300,
    chunk_overlap: 50,
    enable_hybrid: false,
    vector_weight: 0.7,
    bm25_weight: 0.3,
    use_query_prefix: true,
    use_passage_prefix: true,
    show_timing: true,
    show_embeddings: false,
  });

  // Available collections
  const [collections, setCollections] = useState<string[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);

  const presets = {
    default: {
      max_results: 10,
      score_threshold: 0.3,
      chunk_size: 300,
      chunk_overlap: 50,
      enable_hybrid: false,
      vector_weight: 0.7,
      bm25_weight: 0.3,
    },
    high_precision: {
      max_results: 5,
      score_threshold: 0.5,
      chunk_size: 200,
      chunk_overlap: 30,
      enable_hybrid: true,
      vector_weight: 0.8,
      bm25_weight: 0.2,
    },
    high_recall: {
      max_results: 20,
      score_threshold: 0.1,
      chunk_size: 400,
      chunk_overlap: 100,
      enable_hybrid: true,
      vector_weight: 0.6,
      bm25_weight: 0.4,
    },
    hybrid: {
      max_results: 10,
      score_threshold: 0.2,
      chunk_size: 300,
      chunk_overlap: 50,
      enable_hybrid: true,
      vector_weight: 0.5,
      bm25_weight: 0.5,
    },
  };

  useEffect(() => {
    // Check if we have tokens in localStorage but not in tokenManager
    const syncTokens = async () => {
      const rawTokens = localStorage.getItem('auth_tokens');
      if (rawTokens && !tokenManager.isAuthenticated()) {
        try {
          const tokens = JSON.parse(rawTokens);
          // Sync tokens to tokenManager
          tokenManager.setTokens(
            tokens.access_token,
            tokens.refresh_token,
            Math.floor((tokens.access_expires_at - Date.now()) / 1000)
          );
          console.log('RAG Demo: Tokens synced from localStorage to tokenManager');
        } catch (e) {
          console.error('RAG Demo: Failed to sync tokens:', e);
        }
      }
      loadCollections();
    };

    syncTokens();
  }, [user]);

  const loadCollections = async () => {
    setCollectionsLoading(true);
    try {
      console.log('RAG Demo: Loading collections...');
      console.log('RAG Demo: User authenticated:', !!user);
      console.log('RAG Demo: TokenManager authenticated:', tokenManager.isAuthenticated());

      const token = await tokenManager.getAccessToken();
      console.log('RAG Demo: Token retrieved:', token ? 'Yes' : 'No');
      console.log('RAG Demo: Token expiry:', tokenManager.getTokenExpiry());

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        console.log('RAG Demo: Authorization header set');
      } else {
        console.warn('RAG Demo: No token available');
      }

      const response = await fetch('/api/rag/debug/collections', { headers });
      console.log('RAG Demo: Collections response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('RAG Demo: Collections loaded:', data.collections);
        setCollections(data.collections || []);
        // Auto-select first collection if none selected
        if (data.collections && data.collections.length > 0 && !config.collection_name) {
          setConfig(prev => ({ ...prev, collection_name: data.collections[0] }));
        }
      } else {
        const errorText = await response.text();
        console.error('RAG Demo: Collections failed:', response.status, errorText);
      }
    } catch (err) {
      console.error('RAG Demo: Failed to load collections:', err);
    } finally {
      setCollectionsLoading(false);
    }
  };

  const loadPreset = (presetName: keyof typeof presets) => {
    setConfig(prev => ({
      ...prev,
      ...presets[presetName],
    }));
  };

  const performSearch = async () => {
    if (!query.trim()) return;
    if (!config.collection_name) {
      setError('Please select a collection');
      return;
    }

    setIsLoading(true);
    setError('');
    setResults([]);

    try {
      const token = await tokenManager.getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch('/api/rag/debug/search', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query,
          max_results: config.max_results,
          score_threshold: config.score_threshold,
          collection_name: config.collection_name,
          config,
        }),
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data.results || []);
      setDebugInfo(data.debug_info || {});
      setSearchTime(data.search_time_ms || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const updateConfig = (key: string, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">RAG Demo</h1>
          <p>Please log in to access the RAG demo interface.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <h1 className="text-3xl font-bold mb-2">🔍 RAG Search Demo</h1>
      <p className="text-gray-600 mb-6">Test and tune your RAG system with real-time search and debugging</p>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Search Results - Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Preset Buttons */}
          <div className="flex flex-wrap gap-2">
            {Object.entries(presets).map(([name, _]) => (
              <button
                key={name}
                onClick={() => loadPreset(name as keyof typeof presets)}
                className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-md text-sm capitalize"
              >
                {name.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && performSearch()}
                placeholder="Enter your search query..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={performSearch}
                disabled={isLoading || !config.collection_name}
                className="px-6 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
              >
                {isLoading ? 'Searching...' : 'Search'}
              </button>
            </div>

            {error && (
              <div className="mt-4 p-4 bg-red-100 text-red-700 rounded-md">
                Error: {error}
              </div>
            )}

            {/* Results Summary */}
            {results.length > 0 && (
              <div className="mt-4 p-3 bg-blue-50 rounded-md">
                <p className="text-sm">
                  Found <strong>{results.length}</strong> results in <strong>{searchTime.toFixed(0)}ms</strong>
                  {config.enable_hybrid && (
                    <span className="ml-2 text-green-600">• Hybrid Search Enabled</span>
                  )}
                </p>
              </div>
            )}
          </div>

          {/* Search Results */}
          <div className="space-y-4">
            {results.map((result, index) => (
              <div key={index} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start mb-3">
                  <h3 className="text-lg font-semibold">Result {index + 1}</h3>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    result.score >= 0.5 ? 'bg-green-100 text-green-800' :
                    result.score >= 0.3 ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    Score: {result.score.toFixed(4)}
                  </span>
                </div>

                <div className="text-gray-700 mb-4 whitespace-pre-wrap">
                  {result.document.content}
                </div>

                {/* Metadata */}
                <div className="text-sm text-gray-500 mb-3">
                  {result.document.metadata.content_type && (
                    <span>Type: {result.document.metadata.content_type}</span>
                  )}
                  {result.document.metadata.language && (
                    <span className="ml-3">Language: {result.document.metadata.language}</span>
                  )}
                  {result.document.metadata.filename && (
                    <span className="ml-3">File: {result.document.metadata.filename}</span>
                  )}
                  {result.document.metadata.chunk_index !== undefined && (
                    <span className="ml-3">
                      Chunk: {result.document.metadata.chunk_index + 1}/{result.document.metadata.chunk_count || '?'}
                    </span>
                  )}
                </div>

                {/* Debug Details */}
                {config.show_timing && result.debug_info && (
                  <div className="mt-4 p-3 bg-gray-50 rounded-md text-xs font-mono">
                    <p><strong>Debug Information:</strong></p>
                    {result.debug_info.vector_score !== undefined && (
                      <p>Vector Score: {result.debug_info.vector_score.toFixed(4)}</p>
                    )}
                    {result.debug_info.bm25_score !== undefined && (
                      <p>BM25 Score: {result.debug_info.bm25_score.toFixed(4)}</p>
                    )}
                    {result.document.metadata.question && (
                      <div className="mt-2">
                        <p><strong>Question:</strong> {result.document.metadata.question}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Debug Section */}
          {debugInfo && Object.keys(debugInfo).length > 0 && (
            <div className="bg-gray-900 text-green-400 rounded-lg shadow p-6 font-mono text-sm">
              <h3 className="text-lg font-semibold mb-4">Debug Information</h3>

              {debugInfo.score_stats && (
                <div className="mb-4">
                  <p className="font-semibold mb-2">Score Statistics:</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div>Min: {debugInfo.score_stats.min?.toFixed(4)}</div>
                    <div>Max: {debugInfo.score_stats.max?.toFixed(4)}</div>
                    <div>Avg: {debugInfo.score_stats.avg?.toFixed(4)}</div>
                    <div>StdDev: {debugInfo.score_stats.stddev?.toFixed(4)}</div>
                  </div>
                </div>
              )}

              {debugInfo.collection_stats && (
                <div className="mb-4">
                  <p className="font-semibold mb-2">Collection Stats:</p>
                  <div className="text-xs">
                    <p>Total Documents: {debugInfo.collection_stats.total_documents}</p>
                    <p>Total Chunks: {debugInfo.collection_stats.total_chunks}</p>
                    <p>Languages: {debugInfo.collection_stats.languages?.join(', ')}</p>
                  </div>
                </div>
              )}

              {debugInfo.query_embedding && config.show_embeddings && (
                <div>
                  <p className="font-semibold mb-2">Query Embedding (first 10 dims):</p>
                  <p className="text-xs">
                    [{debugInfo.query_embedding.slice(0, 10).map(x => x.toFixed(6)).join(', ')}...]
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Configuration Panel */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">⚙️ Configuration</h2>

            <div className="space-y-4">
              {/* Search Settings */}
              <div>
                <h3 className="font-medium mb-2">Search Settings</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm mb-1">Max Results: {config.max_results}</label>
                    <input
                      type="range"
                      min="1"
                      max="50"
                      value={config.max_results}
                      onChange={(e) => updateConfig('max_results', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm mb-1">Score Threshold: {config.score_threshold}</label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={config.score_threshold}
                      onChange={(e) => updateConfig('score_threshold', parseFloat(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm mb-1">Collection Name</label>
                    {collectionsLoading ? (
                      <select
                        disabled
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm bg-gray-50"
                      >
                        <option>Loading collections...</option>
                      </select>
                    ) : (
                      <select
                        value={config.collection_name}
                        onChange={(e) => updateConfig('collection_name', e.target.value)}
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="">Select a collection...</option>
                        {collections.map(collection => (
                          <option key={collection} value={collection}>
                            {collection}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
              </div>

              {/* Chunking Settings */}
              <div>
                <h3 className="font-medium mb-2">Chunking Settings</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm mb-1">Chunk Size: {config.chunk_size}</label>
                    <input
                      type="range"
                      min="100"
                      max="1000"
                      step="50"
                      value={config.chunk_size}
                      onChange={(e) => updateConfig('chunk_size', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm mb-1">Chunk Overlap: {config.chunk_overlap}</label>
                    <input
                      type="range"
                      min="0"
                      max="200"
                      step="10"
                      value={config.chunk_overlap}
                      onChange={(e) => updateConfig('chunk_overlap', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>
                </div>
              </div>

              {/* Hybrid Search */}
              <div>
                <h3 className="font-medium mb-2">Hybrid Search</h3>
                <div className="space-y-3">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={config.enable_hybrid}
                      onChange={(e) => updateConfig('enable_hybrid', e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Enable Hybrid Search</span>
                  </label>
                  {config.enable_hybrid && (
                    <>
                      <div>
                        <label className="block text-sm mb-1">Vector Weight: {config.vector_weight}</label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={config.vector_weight}
                          onChange={(e) => updateConfig('vector_weight', parseFloat(e.target.value))}
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block text-sm mb-1">BM25 Weight: {config.bm25_weight}</label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={config.bm25_weight}
                          onChange={(e) => updateConfig('bm25_weight', parseFloat(e.target.value))}
                          className="w-full"
                        />
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Debug Options */}
              <div>
                <h3 className="font-medium mb-2">Debug Options</h3>
                <div className="space-y-2">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={config.show_timing}
                      onChange={(e) => updateConfig('show_timing', e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Show Timing</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={config.show_embeddings}
                      onChange={(e) => updateConfig('show_embeddings', e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Show Embeddings</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}