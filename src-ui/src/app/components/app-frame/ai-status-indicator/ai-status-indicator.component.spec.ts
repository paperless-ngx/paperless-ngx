import { ComponentFixture, TestBed } from '@angular/core/testing'
import { Router } from '@angular/router'
import { of } from 'rxjs'
import { AIStatus } from 'src/app/data/ai-status'
import { AIStatusService } from 'src/app/services/ai-status.service'
import { AIStatusIndicatorComponent } from './ai-status-indicator.component'

describe('AIStatusIndicatorComponent', () => {
  let component: AIStatusIndicatorComponent
  let fixture: ComponentFixture<AIStatusIndicatorComponent>
  let aiStatusService: jasmine.SpyObj<AIStatusService>
  let router: jasmine.SpyObj<Router>

  const mockAIStatus: AIStatus = {
    active: true,
    processing: false,
    documents_scanned_today: 42,
    suggestions_applied: 15,
    pending_deletion_requests: 2,
    last_scan: '2025-11-15T12:00:00Z',
    version: '1.0.0',
  }

  beforeEach(async () => {
    const aiStatusServiceSpy = jasmine.createSpyObj('AIStatusService', [
      'getStatus',
      'getCurrentStatus',
      'refresh',
    ])
    const routerSpy = jasmine.createSpyObj('Router', ['navigate'])

    aiStatusServiceSpy.getStatus.and.returnValue(of(mockAIStatus))
    aiStatusServiceSpy.getCurrentStatus.and.returnValue(mockAIStatus)

    await TestBed.configureTestingModule({
      imports: [AIStatusIndicatorComponent],
      providers: [
        { provide: AIStatusService, useValue: aiStatusServiceSpy },
        { provide: Router, useValue: routerSpy },
      ],
    }).compileComponents()

    aiStatusService = TestBed.inject(
      AIStatusService
    ) as jasmine.SpyObj<AIStatusService>
    router = TestBed.inject(Router) as jasmine.SpyObj<Router>

    fixture = TestBed.createComponent(AIStatusIndicatorComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should subscribe to AI status on init', () => {
    expect(aiStatusService.getStatus).toHaveBeenCalled()
    expect(component.aiStatus).toEqual(mockAIStatus)
  })

  it('should show robot icon', () => {
    expect(component.iconName).toBe('robot')
  })

  it('should have active class when AI is active', () => {
    component.aiStatus = { ...mockAIStatus, active: true, processing: false }
    expect(component.iconClass).toContain('active')
  })

  it('should have inactive class when AI is inactive', () => {
    component.aiStatus = { ...mockAIStatus, active: false }
    expect(component.iconClass).toContain('inactive')
  })

  it('should have processing class when AI is processing', () => {
    component.aiStatus = { ...mockAIStatus, active: true, processing: true }
    expect(component.iconClass).toContain('processing')
  })

  it('should show alerts when there are pending deletion requests', () => {
    component.aiStatus = { ...mockAIStatus, pending_deletion_requests: 2 }
    expect(component.hasAlerts).toBe(true)
  })

  it('should not show alerts when there are no pending deletion requests', () => {
    component.aiStatus = { ...mockAIStatus, pending_deletion_requests: 0 }
    expect(component.hasAlerts).toBe(false)
  })

  it('should navigate to settings when navigateToSettings is called', () => {
    component.navigateToSettings()
    expect(router.navigate).toHaveBeenCalledWith(['/settings'], {
      fragment: 'ai-scanner',
    })
  })

  it('should unsubscribe on destroy', () => {
    const subscription = component['subscription']
    spyOn(subscription, 'unsubscribe')
    component.ngOnDestroy()
    expect(subscription.unsubscribe).toHaveBeenCalled()
  })
})
