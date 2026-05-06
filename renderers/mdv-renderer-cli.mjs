#!/usr/bin/env node
import { createServer } from 'node:http'
import { createReadStream, existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = ''
    process.stdin.setEncoding('utf8')
    process.stdin.on('data', chunk => {
      data += chunk
    })
    process.stdin.on('end', () => resolve(data))
    process.stdin.on('error', reject)
  })
}

function serveArtifact(artifactDir) {
  const root = path.resolve(artifactDir)
  const server = createServer((req, res) => {
    try {
      const requestUrl = new URL(req.url || '/', 'http://127.0.0.1')
      const relativeUrl = requestUrl.pathname === '/' ? '/server-render.html' : requestUrl.pathname
      const decodedPath = decodeURIComponent(relativeUrl)
      const filePath = path.resolve(root, `.${decodedPath}`)

      if (!filePath.startsWith(`${root}${path.sep}`) && filePath !== root) {
        res.writeHead(403)
        res.end('Forbidden')
        return
      }

      if (!existsSync(filePath)) {
        res.writeHead(404)
        res.end('Not found')
        return
      }

      res.writeHead(200, {
        'content-type': MIME_TYPES[path.extname(filePath)] || 'application/octet-stream',
        'cache-control': 'no-store',
      })
      createReadStream(filePath).pipe(res)
    } catch (error) {
      res.writeHead(500)
      res.end(String(error))
    }
  })

  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${address.port}`,
      })
    })
  })
}

function createWarning(code, title, message) {
  return {
    code,
    severity: 'warning',
    title,
    message,
    recoverable: true,
  }
}

function createFailureResult(status, message, outputDir) {
  return {
    schemaVersion: '1.0',
    ok: false,
    status,
    htmlPath: path.join(outputDir, 'rendered.html'),
    images: [],
    warnings: [createWarning(status === 'timeout' ? 'RENDER_TIMEOUT' : 'RENDERER_UNAVAILABLE', '渲染失败', message)],
    stats: {
      totalBlocks: 0,
      renderedBlocks: 0,
      failedBlocks: 0,
      durationMs: 0,
    },
    renderSummary: {
      totalBlocks: 0,
      renderedBlocks: 0,
      failedBlocks: 0,
      warningCount: 1,
      statusText: message,
    },
  }
}

function isLocalUrl(url) {
  try {
    const parsed = new URL(url)
    return ['127.0.0.1', 'localhost', '::1'].includes(parsed.hostname)
  } catch {
    return false
  }
}

function isAllowlistedUrl(url, hosts = []) {
  try {
    const parsed = new URL(url)
    return hosts.includes(parsed.hostname)
  } catch {
    return false
  }
}

async function captureImages(page, pageResult, outputDir) {
  const images = []
  const warnings = []

  for (let index = 0; index < (pageResult.images || []).length; index += 1) {
    const image = pageResult.images[index]
    const locator = page.locator(image.selector).first()
    const pngPath = path.join(outputDir, `chart-${String(index + 1).padStart(3, '0')}-${image.type}.png`)

    try {
      await locator.screenshot({ path: pngPath, animations: 'disabled' })
      const box = await locator.boundingBox()
      images.push({
        id: image.id,
        type: image.type,
        pngPath,
        widthPx: Math.max(1, Math.round(box?.width || image.widthPx || 1)),
        heightPx: Math.max(1, Math.round(box?.height || image.heightPx || 1)),
        widthCm: image.widthCm || 15.5,
        durationMs: image.durationMs || 0,
        sourceIndex: Number.isFinite(image.sourceIndex) ? image.sourceIndex : undefined,
      })
    } catch (error) {
      warnings.push(createWarning(
        'SCREENSHOT_FAILED',
        '图表截图失败',
        `第 ${index + 1} 个 ${image.type} 图表截图失败：${String(error).slice(0, 300)}`,
      ))
    }
  }

  return { images, warnings }
}

async function main() {
  const startedAt = Date.now()
  const raw = await readStdin()
  const input = JSON.parse(raw)
  const outputDir = path.resolve(input.outputDir)
  const artifactDir = path.resolve(input.artifactDir || process.env.MDV_RENDER_ARTIFACT_DIR || '/app/renderers/dist/server-render')
  const renderTimeoutMs = input.timeoutMs || Number(process.env.MDV_RENDER_TIMEOUT_MS || 60000)
  const timeoutMs = renderTimeoutMs + 3000

  await mkdir(outputDir, { recursive: true })
  const htmlPath = path.join(outputDir, 'rendered.html')

  let browser
  let server
  try {
    const served = await serveArtifact(artifactDir)
    server = served.server

    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1200 },
      deviceScaleFactor: 3,
    })

    await context.route('**/*', route => {
      const url = route.request().url()
      if (url.startsWith(served.baseUrl) || url.startsWith('data:') || url.startsWith('blob:')) {
        route.continue()
        return
      }
      if (input.networkPolicy === 'local-friendly' && isLocalUrl(url)) {
        route.continue()
        return
      }
      if (input.networkPolicy === 'allowlist' && isAllowlistedUrl(url, input.allowlistHosts || [])) {
        route.continue()
        return
      }
      route.abort()
    })

    const page = await context.newPage()
    page.setDefaultTimeout(timeoutMs)
    await page.addInitScript(renderInput => {
      window.__MDV_RENDER_INPUT__ = renderInput
      window.__MDV_RENDER_DONE__ = false
      window.__MDV_RENDER_RESULT__ = undefined
    }, input)

    await page.goto(`${served.baseUrl}/server-render.html`, { waitUntil: 'domcontentloaded', timeout: timeoutMs })
    await page.waitForFunction(() => window.__MDV_RENDER_DONE__ === true, undefined, { timeout: timeoutMs })

    const pageResult = await page.evaluate(() => window.__MDV_RENDER_RESULT__)
    if (!pageResult) {
      throw new Error('renderer page did not provide __MDV_RENDER_RESULT__')
    }

    const html = pageResult.html || await page.content()
    await writeFile(htmlPath, html, 'utf8')
    const captureResult = await captureImages(page, pageResult, outputDir)
    const warnings = [...(pageResult.warnings || []), ...captureResult.warnings]
    const failedScreenshots = (pageResult.images || []).length - captureResult.images.length
    const status = pageResult.status === 'success' && failedScreenshots > 0 ? 'partial' : pageResult.status
    const stats = {
      ...pageResult.stats,
      failedBlocks: (pageResult.stats?.failedBlocks || 0) + failedScreenshots,
      durationMs: Date.now() - startedAt,
    }

    const result = {
      schemaVersion: '1.0',
      ok: pageResult.ok && failedScreenshots === 0,
      status,
      htmlPath,
      images: captureResult.images,
      warnings,
      stats,
      renderSummary: {
        totalBlocks: stats.totalBlocks || 0,
        renderedBlocks: captureResult.images.length,
        failedBlocks: stats.failedBlocks || 0,
        warningCount: warnings.length,
        statusText: status,
      },
    }

    process.stdout.write(`${JSON.stringify(result)}\n`)
  } catch (error) {
    const message = String(error?.message || error)
    const status = /timeout/i.test(message) ? 'timeout' : 'failed'
    await writeFile(htmlPath, '', 'utf8').catch(() => {})
    process.stdout.write(`${JSON.stringify(createFailureResult(status, message, outputDir))}\n`)
  } finally {
    if (browser) {
      await browser.close().catch(() => {})
    }
    if (server) {
      await new Promise(resolve => server.close(resolve))
    }
  }
}

main().catch(error => {
  process.stderr.write(`${String(error?.stack || error)}\n`)
  process.exit(1)
})
