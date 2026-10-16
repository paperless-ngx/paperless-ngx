import { ComponentFixture, TestBed } from '@angular/core/testing'
import { provideRouter } from '@angular/router'
import { of, throwError } from 'rxjs'
import { DocumentReviewService } from 'src/app/services/rest/document-review.service'
import { ReviewQueueComponent } from './review-queue.component'

describe('ReviewQueueComponent', () => {
  let fixture: ComponentFixture<ReviewQueueComponent>
  let component: ReviewQueueComponent
  let service: { queue: jest.Mock }

  beforeEach(async () => {
    service = {
      queue: jest.fn().mockReturnValue(
        of({
          count: 21,
          results: [
            {
              document: 10,
              state: 'pending',
              revision: 1,
              reviewer: 2,
              title: 'Synthetic document',
            },
          ],
        })
      ),
    }
    await TestBed.configureTestingModule({
      imports: [ReviewQueueComponent],
      providers: [
        provideRouter([]),
        { provide: DocumentReviewService, useValue: service },
      ],
    }).compileComponents()
    fixture = TestBed.createComponent(ReviewQueueComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    await fixture.whenStable()
  })

  it('loads pending records and links to the document review tab', () => {
    expect(service.queue).toHaveBeenCalledWith('pending', null, 1)
    expect(
      fixture.nativeElement.querySelector('tbody a').getAttribute('href')
    ).toBe('/documents/10/review')
  })

  it('paginates and resets the page when state and reviewer filters change', () => {
    component.nextPage(1)
    expect(service.queue).toHaveBeenLastCalledWith('pending', null, 2)
    component.state = 'rejected'
    component.reviewer = 2
    component.load(true)
    expect(service.queue).toHaveBeenLastCalledWith('rejected', 2, 1)
    expect(component.page).toBe(1)
  })

  it('validates reviewer IDs before making a request', () => {
    component.reviewer = -1
    component.load(true)
    expect(service.queue).toHaveBeenCalledTimes(1)
    expect(component.error()).toContain('positive reviewer ID')
  })

  it('allows a successful retry after a failed filter request', () => {
    service.queue.mockReturnValueOnce(throwError(() => new Error('offline')))
    component.load()
    expect(component.error()).toContain('Unable to load')
    component.load()
    expect(component.error()).toBe('')
    expect(component.queue().count).toBe(21)
  })

  it('renders an empty queue', () => {
    service.queue.mockReturnValue(of({ count: 0, results: [] }))
    component.load()
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('No documents match')
  })
})
