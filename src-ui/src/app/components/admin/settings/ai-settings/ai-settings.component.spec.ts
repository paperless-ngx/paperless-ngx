import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { of } from 'rxjs'
import { AiSettingsComponent } from './ai-settings.component'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'

describe('AiSettingsComponent', () => {
  let component: AiSettingsComponent
  let fixture: ComponentFixture<AiSettingsComponent>
  let mockSettingsService: jasmine.SpyObj<SettingsService>
  let mockToastService: jasmine.SpyObj<ToastService>

  beforeEach(async () => {
    mockSettingsService = jasmine.createSpyObj('SettingsService', ['get', 'set'])
    mockToastService = jasmine.createSpyObj('ToastService', ['show', 'showError'])

    await TestBed.configureTestingModule({
      imports: [AiSettingsComponent, ReactiveFormsModule],
      providers: [
        { provide: SettingsService, useValue: mockSettingsService },
        { provide: ToastService, useValue: mockToastService },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(AiSettingsComponent)
    component = fixture.componentInstance
    
    // Create a mock form group
    component.settingsForm = new FormGroup({
      aiScannerEnabled: new FormControl(false),
      aiMlFeaturesEnabled: new FormControl(false),
      aiAdvancedOcrEnabled: new FormControl(false),
      aiAutoApplyThreshold: new FormControl(80),
      aiSuggestThreshold: new FormControl(60),
      aiMlModel: new FormControl('bert-base'),
    })
    
    component.isDirty$ = of(false)
    
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should initialize with default AI statistics', () => {
    expect(component.aiStats).toBeDefined()
    expect(component.aiStats.totalDocumentsProcessed).toBe(0)
    expect(component.aiStats.autoAppliedCount).toBe(0)
    expect(component.aiStats.suggestionsCount).toBe(0)
  })

  it('should have ML model options', () => {
    expect(component.mlModels.length).toBeGreaterThan(0)
    expect(component.mlModels[0].value).toBe('bert-base')
  })

  it('should update auto-apply threshold', () => {
    const event = {
      target: { value: '85' },
    } as any
    
    component.onAutoApplyThresholdChange(event)
    
    expect(component.settingsForm.get('aiAutoApplyThreshold')?.value).toBe(85)
  })

  it('should update suggest threshold', () => {
    const event = {
      target: { value: '70' },
    } as any
    
    component.onSuggestThresholdChange(event)
    
    expect(component.settingsForm.get('aiSuggestThreshold')?.value).toBe(70)
  })

  it('should emit settings changed event', () => {
    spyOn(component.settingsChanged, 'emit')
    
    component.onAiSettingChange()
    
    expect(component.settingsChanged.emit).toHaveBeenCalled()
  })

  it('should test AI with sample document', (done) => {
    component.settingsForm.get('aiScannerEnabled')?.setValue(true)
    
    expect(component.testingInProgress).toBe(false)
    
    component.testAIWithSample()
    
    expect(component.testingInProgress).toBe(true)
    
    setTimeout(() => {
      expect(component.testingInProgress).toBe(false)
      expect(mockToastService.show).toHaveBeenCalled()
      done()
    }, 2100)
  })

  it('should return correct aiScannerEnabled status', () => {
    component.settingsForm.get('aiScannerEnabled')?.setValue(true)
    expect(component.aiScannerEnabled).toBe(true)
    
    component.settingsForm.get('aiScannerEnabled')?.setValue(false)
    expect(component.aiScannerEnabled).toBe(false)
  })

  it('should get correct threshold values', () => {
    component.settingsForm.get('aiAutoApplyThreshold')?.setValue(75)
    component.settingsForm.get('aiSuggestThreshold')?.setValue(55)
    
    expect(component.autoApplyThreshold).toBe(75)
    expect(component.suggestThreshold).toBe(55)
  })
})
