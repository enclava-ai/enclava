/**
 * Unit tests for SourcesList component
 *
 * Tests cover:
 * - Component renders correctly with sources
 * - URLs are clickable and properly formatted
 * - Non-URL sources display correctly
 * - Accessibility attributes are present
 * - Responsive behavior and edge cases
 *
 * NOTE: This test requires Jest and React Testing Library to be installed:
 *
 * npm install --save-dev @testing-library/react @testing-library/jest-dom jest jest-environment-jsdom
 * npm install --save-dev @testing-library/user-event
 *
 * Also add to package.json:
 * "scripts": {
 *   "test": "jest",
 *   "test:watch": "jest --watch",
 *   "test:coverage": "jest --coverage"
 * }
 *
 * Create jest.config.js in frontend root:
 * module.exports = {
 *   testEnvironment: 'jsdom',
 *   setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
 *   moduleNameMapper: {
 *     '^@/(.*)$': '<rootDir>/src/$1',
 *   },
 * }
 *
 * Create jest.setup.js in frontend root:
 * import '@testing-library/jest-dom'
 */

import React from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { SourcesList } from './SourcesList'
import { ChatMessageSource } from '@/types/chatbot'

// Mock the lucide-react icons
jest.mock('lucide-react', () => ({
  ExternalLink: ({ className, 'aria-hidden': ariaHidden }: any) => (
    <span data-testid="external-link-icon" className={className} aria-hidden={ariaHidden}>
      ↗
    </span>
  ),
  Globe: ({ className, 'aria-hidden': ariaHidden }: any) => (
    <span data-testid="globe-icon" className={className} aria-hidden={ariaHidden}>
      🌐
    </span>
  ),
}))

// Mock the Badge component
jest.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className, variant, 'aria-label': ariaLabel }: any) => (
    <span
      data-testid="badge"
      data-variant={variant}
      className={className}
      aria-label={ariaLabel}
    >
      {children}
    </span>
  ),
}))

describe('SourcesList Component', () => {
  const mockSourceWithUrl: ChatMessageSource = {
    title: 'How to reset password?',
    content: 'Full content here',
    url: 'https://support.example.com/faq/password-reset',
    language: 'EN',
    article_id: 'faq123',
    relevance_score: 0.95,
    content_preview: 'To reset your password, go to settings...',
  }

  const mockSourceWithoutUrl: ChatMessageSource = {
    title: 'Security Best Practices',
    content: 'Full content here',
    url: null,
    relevance_score: 0.82,
    content_preview: 'Always use strong passwords...',
  }

  const mockSourceNonEnglish: ChatMessageSource = {
    title: 'Wie setze ich mein Passwort zurück?',
    content: 'Full content here',
    url: 'https://support.example.com/de/faq/password',
    language: 'DE',
    relevance_score: 0.88,
  }

  describe('Rendering', () => {
    it('should render null when sources array is empty', () => {
      const { container } = render(<SourcesList sources={[]} />)
      expect(container.firstChild).toBeNull()
    })

    it('should render null when sources is null/undefined', () => {
      const { container: container1 } = render(<SourcesList sources={null as any} />)
      expect(container1.firstChild).toBeNull()

      const { container: container2 } = render(<SourcesList sources={undefined as any} />)
      expect(container2.firstChild).toBeNull()
    })

    it('should render sources list with correct heading', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      expect(screen.getByText(/Sources \(1\):/)).toBeInTheDocument()
    })

    it('should render multiple sources', () => {
      render(<SourcesList sources={[mockSourceWithUrl, mockSourceWithoutUrl]} />)

      expect(screen.getByText(/Sources \(2\):/)).toBeInTheDocument()
      expect(screen.getByText('How to reset password?')).toBeInTheDocument()
      expect(screen.getByText('Security Best Practices')).toBeInTheDocument()
    })

    it('should render with correct ARIA region', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const region = screen.getByRole('region', { name: 'Information sources' })
      expect(region).toBeInTheDocument()
    })
  })

  describe('Sources with URLs', () => {
    it('should render source with URL as clickable link', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const link = screen.getByRole('link', { name: /How to reset password\?/i })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', 'https://support.example.com/faq/password-reset')
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    })

    it('should display external link icon for URLs', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const icon = screen.getByTestId('external-link-icon')
      expect(icon).toBeInTheDocument()
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })

    it('should have proper ARIA label for link', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const link = screen.getByRole('link')
      expect(link).toHaveAttribute(
        'aria-label',
        'Open source: How to reset password? (opens in new tab)'
      )
    })

    it('should be keyboard accessible (focusable)', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const link = screen.getByRole('link')
      expect(link).toHaveClass('focus:ring-2')
      expect(link).toHaveClass('focus:ring-primary')
    })
  })

  describe('Sources without URLs', () => {
    it('should render source without URL as plain text', () => {
      render(<SourcesList sources={[mockSourceWithoutUrl]} />)

      // Should not be a link
      expect(screen.queryByRole('link')).not.toBeInTheDocument()

      // Should be plain text
      const title = screen.getByText('Security Best Practices')
      expect(title.tagName).toBe('SPAN')
    })

    it('should not display external link icon for non-URL sources', () => {
      render(<SourcesList sources={[mockSourceWithoutUrl]} />)

      expect(screen.queryByTestId('external-link-icon')).not.toBeInTheDocument()
    })

    it('should handle empty URL string as non-URL', () => {
      const sourceWithEmptyUrl = { ...mockSourceWithUrl, url: '' }
      render(<SourcesList sources={[sourceWithEmptyUrl]} />)

      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })

    it('should handle whitespace-only URL as non-URL', () => {
      const sourceWithWhitespaceUrl = { ...mockSourceWithUrl, url: '   ' }
      render(<SourcesList sources={[sourceWithWhitespaceUrl]} />)

      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })
  })

  describe('Language Badges', () => {
    it('should display language badge for non-English sources', () => {
      render(<SourcesList sources={[mockSourceNonEnglish]} />)

      const badge = screen.getByText('DE')
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveAttribute('aria-label', 'Language: DE')
    })

    it('should not display language badge for English sources', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      expect(screen.queryByTestId('globe-icon')).not.toBeInTheDocument()
    })

    it('should display globe icon for non-English sources', () => {
      render(<SourcesList sources={[mockSourceNonEnglish]} />)

      const icon = screen.getByTestId('globe-icon')
      expect(icon).toBeInTheDocument()
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })

    it('should uppercase language code', () => {
      const sourceLowercase = { ...mockSourceNonEnglish, language: 'de' }
      render(<SourcesList sources={[sourceLowercase]} />)

      expect(screen.getByText('DE')).toBeInTheDocument()
    })
  })

  describe('Relevance Score', () => {
    it('should display relevance score as percentage', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const scoreBadge = screen.getByText('95%')
      expect(scoreBadge).toBeInTheDocument()
    })

    it('should have ARIA label for relevance score', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const scoreBadge = screen.getByLabelText('Relevance score: 95%')
      expect(scoreBadge).toBeInTheDocument()
    })

    it('should round relevance score to integer', () => {
      const sourceWithDecimal = { ...mockSourceWithUrl, relevance_score: 0.876 }
      render(<SourcesList sources={[sourceWithDecimal]} />)

      expect(screen.getByText('88%')).toBeInTheDocument()
    })

    it('should not display score badge if relevance_score is missing', () => {
      const sourceNoScore = { ...mockSourceWithUrl, relevance_score: undefined }
      render(<SourcesList sources={[sourceNoScore]} />)

      expect(screen.queryByText(/%$/)).not.toBeInTheDocument()
    })

    it('should handle zero relevance score', () => {
      const sourceZeroScore = { ...mockSourceWithUrl, relevance_score: 0 }
      render(<SourcesList sources={[sourceZeroScore]} />)

      expect(screen.getByText('0%')).toBeInTheDocument()
    })

    it('should handle 100% relevance score', () => {
      const sourcePerfectScore = { ...mockSourceWithUrl, relevance_score: 1.0 }
      render(<SourcesList sources={[sourcePerfectScore]} />)

      expect(screen.getByText('100%')).toBeInTheDocument()
    })
  })

  describe('Content Preview', () => {
    it('should display content preview when available', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      expect(screen.getByText('To reset your password, go to settings...')).toBeInTheDocument()
    })

    it('should not display preview when not available', () => {
      const sourceNoPreview = { ...mockSourceWithUrl, content_preview: undefined }
      render(<SourcesList sources={[sourceNoPreview]} />)

      expect(screen.queryByText(/reset your password/)).not.toBeInTheDocument()
    })

    it('should have line-clamp class for preview text', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const preview = screen.getByText('To reset your password, go to settings...')
      expect(preview).toHaveClass('line-clamp-2')
    })
  })

  describe('Fallback Titles', () => {
    it('should use fallback title when title is missing', () => {
      const sourceNoTitle = { ...mockSourceWithUrl, title: '' }
      render(<SourcesList sources={[sourceNoTitle]} />)

      expect(screen.getByText('Source 1')).toBeInTheDocument()
    })

    it('should use correct index for fallback titles', () => {
      const source1 = { ...mockSourceWithUrl, title: '' }
      const source2 = { ...mockSourceWithoutUrl, title: '' }
      render(<SourcesList sources={[source1, source2]} />)

      expect(screen.getByText('Source 1')).toBeInTheDocument()
      expect(screen.getByText('Source 2')).toBeInTheDocument()
    })
  })

  describe('Responsive Behavior', () => {
    it('should have break-words class for long titles', () => {
      const longTitle = 'This is a very long title that should wrap to multiple lines'
      const source = { ...mockSourceWithUrl, title: longTitle }
      render(<SourcesList sources={[source]} />)

      const link = screen.getByRole('link')
      expect(link).toHaveClass('break-words')
    })

    it('should have flex-wrap for badges container', () => {
      render(<SourcesList sources={[mockSourceNonEnglish]} />)

      // Find the container with flex and gap classes
      const container = screen.getByLabelText('Language: DE').parentElement
      expect(container).toHaveClass('flex-wrap')
    })
  })

  describe('Mixed Sources', () => {
    it('should render mix of sources with and without URLs', () => {
      render(<SourcesList sources={[mockSourceWithUrl, mockSourceWithoutUrl, mockSourceNonEnglish]} />)

      // Should have 2 links (with URLs) and 1 span (without URL)
      const links = screen.getAllByRole('link')
      expect(links).toHaveLength(2)

      // All titles should be present
      expect(screen.getByText('How to reset password?')).toBeInTheDocument()
      expect(screen.getByText('Security Best Practices')).toBeInTheDocument()
      expect(screen.getByText('Wie setze ich mein Passwort zurück?')).toBeInTheDocument()
    })

    it('should handle sources with partial data', () => {
      const partialSource: ChatMessageSource = {
        title: 'Minimal Source',
        content: 'Content',
      }
      render(<SourcesList sources={[partialSource]} />)

      expect(screen.getByText('Minimal Source')).toBeInTheDocument()
      // Should not crash and should render without optional fields
    })
  })

  describe('Accessibility', () => {
    it('should have semantic HTML structure', () => {
      const { container } = render(<SourcesList sources={[mockSourceWithUrl]} />)

      // Should have region role
      expect(screen.getByRole('region')).toBeInTheDocument()

      // Links should be properly marked up
      const link = screen.getByRole('link')
      expect(link).toHaveAttribute('href')
    })

    it('should have proper color contrast classes', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const title = screen.getByText(/Sources \(1\)/)
      expect(title).toHaveClass('text-muted-foreground')
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<SourcesList sources={[mockSourceWithUrl]} />)

      const link = screen.getByRole('link')

      // Should be focusable with Tab
      await user.tab()
      expect(link).toHaveFocus()
    })

    it('should have aria-hidden on decorative icons', () => {
      render(<SourcesList sources={[mockSourceWithUrl, mockSourceNonEnglish]} />)

      const externalIcon = screen.getByTestId('external-link-icon')
      expect(externalIcon).toHaveAttribute('aria-hidden', 'true')

      const globeIcon = screen.getByTestId('globe-icon')
      expect(globeIcon).toHaveAttribute('aria-hidden', 'true')
    })
  })

  describe('Edge Cases', () => {
    it('should handle very high relevance scores (>1.0)', () => {
      const sourceHighScore = { ...mockSourceWithUrl, relevance_score: 1.5 }
      render(<SourcesList sources={[sourceHighScore]} />)

      // Should display as 150%
      expect(screen.getByText('150%')).toBeInTheDocument()
    })

    it('should handle negative relevance scores', () => {
      const sourceNegativeScore = { ...mockSourceWithUrl, relevance_score: -0.5 }
      render(<SourcesList sources={[sourceNegativeScore]} />)

      // Should still render (as -50%)
      expect(screen.getByText('-50%')).toBeInTheDocument()
    })

    it('should handle URL with special characters', () => {
      const sourceSpecialUrl = {
        ...mockSourceWithUrl,
        url: 'https://example.com/faq?id=123&lang=en#section',
      }
      render(<SourcesList sources={[sourceSpecialUrl]} />)

      const link = screen.getByRole('link')
      expect(link).toHaveAttribute('href', 'https://example.com/faq?id=123&lang=en#section')
    })

    it('should handle very long content previews', () => {
      const longPreview = 'A'.repeat(500)
      const sourceLongPreview = { ...mockSourceWithUrl, content_preview: longPreview }
      render(<SourcesList sources={[sourceLongPreview]} />)

      const preview = screen.getByText(longPreview)
      expect(preview).toHaveClass('line-clamp-2')
    })
  })

  describe('Source Count Display', () => {
    it('should display correct count for single source', () => {
      render(<SourcesList sources={[mockSourceWithUrl]} />)
      expect(screen.getByText('Sources (1):')).toBeInTheDocument()
    })

    it('should display correct count for multiple sources', () => {
      render(<SourcesList sources={[mockSourceWithUrl, mockSourceWithoutUrl, mockSourceNonEnglish]} />)
      expect(screen.getByText('Sources (3):')).toBeInTheDocument()
    })
  })
})
