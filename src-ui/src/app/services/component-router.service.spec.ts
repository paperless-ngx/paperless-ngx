import { TestBed } from '@angular/core/testing'
import { ActivationStart, Router } from '@angular/router'
import { Subject } from 'rxjs'
import { ComponentRouterService } from './component-router.service'

describe('ComponentRouterService', () => {
  let service: ComponentRouterService
  let router: Router
  let eventsSubject: Subject<any>

  beforeEach(() => {
    eventsSubject = new Subject<any>()
    TestBed.configureTestingModule({
      providers: [
        ComponentRouterService,
        {
          provide: Router,
          useValue: {
            events: eventsSubject.asObservable(),
          },
        },
      ],
    })
    service = TestBed.inject(ComponentRouterService)
    router = TestBed.inject(Router)
  })

  it('should add to history and componentHistory on ActivationStart event', () => {
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url',
        data: { componentName: 'TestComponent' },
      } as any)
    )

    expect((service as any).history).toEqual(['test-url'])
    expect((service as any).componentHistory).toEqual(['TestComponent'])
  })

  it('should not add duplicate component names to componentHistory', () => {
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-1',
        data: { componentName: 'TestComponent' },
      } as any)
    )
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-2',
        data: { componentName: 'TestComponent' },
      } as any)
    )

    expect((service as any).componentHistory.length).toBe(1)
    expect((service as any).componentHistory).toEqual(['TestComponent'])
  })

  it('should return the URL of the component before the current one', () => {
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-1',
        data: { componentName: 'TestComponent1' },
      } as any)
    )
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-2',
        data: { componentName: 'TestComponent2' },
      } as any)
    )

    expect(service.getComponentURLBefore()).toBe('test-url-1')
  })

  it('should update the URL of the current component if the same component is loaded via a different URL', () => {
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-1',
        data: { componentName: 'TestComponent' },
      } as any)
    )
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url-2',
        data: { componentName: 'TestComponent' },
      } as any)
    )

    expect((service as any).history).toEqual(['test-url-2'])
  })

  it('should return null if there is no previous component', () => {
    eventsSubject.next(
      new ActivationStart({
        url: 'test-url',
        data: { componentName: 'TestComponent' },
      } as any)
    )

    expect(service.getComponentURLBefore()).toBeNull()
  })
})
