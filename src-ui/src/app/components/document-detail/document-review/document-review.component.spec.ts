import { HttpErrorResponse } from '@angular/common/http'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { of, throwError } from 'rxjs'
import { DocumentReview } from 'src/app/data/document-review'
import { DocumentReviewService } from 'src/app/services/rest/document-review.service'
import { DocumentReviewComponent } from './document-review.component'

const initial: DocumentReview = {
  document: 10,
  state: 'unreviewed',
  revision: 0,
  reviewer: null,
  submitted_by: null,
  history: [],
}

describe('DocumentReviewComponent', () => {
  let fixture: ComponentFixture<DocumentReviewComponent>
  let component: DocumentReviewComponent
  let service: { get: jest.Mock; options: jest.Mock; mutate: jest.Mock }

  beforeEach(async () => {
    service = {
      get: jest.fn().mockReturnValue(of(initial)),
      options: jest.fn().mockReturnValue(
        of({
          allowed_actions: ['submit'],
          results: [{ id: 2, username: 'reviewer' }],
        })
      ),
      mutate: jest
        .fn()
        .mockReturnValue(of({ ...initial, state: 'pending', revision: 1 })),
    }
    await TestBed.configureTestingModule({
      imports: [DocumentReviewComponent],
      providers: [{ provide: DocumentReviewService, useValue: service }],
    }).compileComponents()
    fixture = TestBed.createComponent(DocumentReviewComponent)
    component = fixture.componentInstance
    fixture.componentRef.setInput('documentId', 10)
    fixture.detectChanges()
    await fixture.whenStable()
  })

  it('shows state, reviewer selection, and only authorized controls', () => {
    const html = fixture.nativeElement as HTMLElement
    expect(html.textContent).toContain('Unreviewed')
    expect(html.querySelector('#reviewer-selection')).not.toBeNull()
    expect(html.textContent).not.toContain('Approve')
    component.options.set({ allowed_actions: [], results: [] })
    fixture.detectChanges()
    expect(html.querySelector('#reviewer-selection')).toBeNull()
  })

  it('submits the selected reviewer with a UUID and expected revision', () => {
    component.reviewer = 2
    component.act('submit')
    expect(service.mutate).toHaveBeenCalledWith(10, {
      action: 'submit',
      reviewer: 2,
      expected_revision: 0,
      request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
    })
  })

  it('safely reuses the request key after a lost response', () => {
    service.mutate.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 0 }))
    )
    component.reviewer = 2
    component.act('submit')
    component.act('submit')
    expect(service.mutate.mock.calls[0][1]).toEqual(
      service.mutate.mock.calls[1][1]
    )
    expect(component.error()).toContain('Retry')
  })

  it('reloads after a conflict without resubmitting', async () => {
    service.get.mockReturnValue(
      of({ ...initial, state: 'pending', revision: 1 })
    )
    service.mutate.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 409 }))
    )
    component.reviewer = 2
    component.act('submit')
    fixture.detectChanges()
    await fixture.whenStable()
    expect(component.error()).toContain('latest state')
    expect(component.review().revision).toBe(1)
    expect(service.mutate).toHaveBeenCalledTimes(1)
  })

  it('rejects only with a trimmed Unicode comment of the permitted length', () => {
    component.options.set({
      allowed_actions: ['approve', 'reject'],
      results: [],
    })
    component.comment = '   '
    component.act('reject')
    expect(service.mutate).not.toHaveBeenCalled()
    component.comment = '😀'.repeat(2001)
    expect(component.validComment).toBe(false)
    component.comment = '  😀'.trimEnd() + '  '
    component.act('reject')
    expect(service.mutate.mock.calls[0][1]).toEqual({
      action: 'reject',
      expected_revision: 0,
      comment: '😀',
      request_id: expect.any(String),
    })
  })

  it.each(['approve', 'reopen'] as const)(
    'sends only permitted fields for %s',
    (action) => {
      component.options.set({ allowed_actions: [action], results: [] })
      component.comment = 'leftover text'
      component.reviewer = 2
      component.act(action)
      expect(service.mutate.mock.calls[0][1]).toEqual({
        action,
        expected_revision: 0,
        request_id: expect.any(String),
      })
    }
  )

  it('renders rejection comments as inert text', () => {
    const comment = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
    component.review.set({
      ...initial,
      history: [
        {
          action: 'reject',
          actor: 2,
          revision: 1,
          at: '2026-01-01T00:00:00Z',
          request_id: null,
          comment,
        },
      ],
    })
    fixture.detectChanges()
    const html = fixture.nativeElement as HTMLElement
    expect(html.textContent).toContain(comment)
    expect(html.querySelector('img, script')).toBeNull()
  })

  it('refreshes when document content is saved', async () => {
    service.get.mockReturnValue(of({ ...initial, revision: 3 }))
    fixture.componentRef.setInput('documentModified', '2026-01-01T01:00:00Z')
    fixture.detectChanges()
    await fixture.whenStable()
    expect(component.review().revision).toBe(3)
  })

  it('searches only the document-scoped eligible reviewer endpoint', () => {
    component.search = 'review'
    component.searchReviewers()
    expect(service.options).toHaveBeenLastCalledWith(10, 'review')
  })

  it('shows a load error without exposing action controls', async () => {
    service.get.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 404 }))
    )
    component.reload()
    fixture.detectChanges()
    await fixture.whenStable()
    expect(component.review()).toBeNull()
    expect(component.options().allowed_actions).toEqual([])
    expect(component.error()).toContain('Unable to load')
  })
})
