import { NextRequest } from 'next/server';

// Proxy at request time, so the same built image works in Docker, local dev,
// and preview hosts. The browser never needs to know the backend hostname.
export const dynamic = 'force-dynamic';

async function proxy(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const base = (process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  const { path: segments } = await params;
  const path = segments.map(segment => encodeURIComponent(segment)).join('/');
  const target = `${base}/v1/${path}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);
  for (const key of ['host', 'connection', 'content-length', 'transfer-encoding']) headers.delete(key);
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      // Node's streaming fetch requires duplex for large multipart uploads.
      duplex: 'half',
      redirect: 'manual',
      cache: 'no-store',
    } as RequestInit & { duplex: 'half' });
    const responseHeaders = new Headers(response.headers);
    for (const key of ['connection', 'content-length', 'transfer-encoding', 'content-encoding']) responseHeaders.delete(key);
    return new Response(response.body, { status: response.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: 'Không thể kết nối dịch vụ backend.' }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
