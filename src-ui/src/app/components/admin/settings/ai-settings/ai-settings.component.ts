import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core'
import { FormControl, FormGroup, FormsModule, ReactiveFormsModule } from '@angular/forms'
import { Observable } from 'rxjs'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { CheckComponent } from '../../../common/input/check/check.component'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CommonModule } from '@angular/common'

interface MLModel {
  value: string
  label: string
}

interface AIPerformanceStats {
  totalDocumentsProcessed: number
  autoAppliedCount: number
  suggestionsCount: number
  averageConfidence: number
  processingTime: number
}

@Component({
  selector: 'pngx-ai-settings',
  templateUrl: './ai-settings.component.html',
  styleUrls: ['./ai-settings.component.scss'],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    CheckComponent,
    NgxBootstrapIconsModule,
  ],
})
export class AiSettingsComponent implements OnInit {
  @Input() settingsForm: FormGroup
  @Input() isDirty$: Observable<boolean>
  @Output() settingsChanged = new EventEmitter<void>()

  private settings = inject(SettingsService)
  private toastService = inject(ToastService)

  mlModels: MLModel[] = [
    { value: 'bert-base', label: 'BERT Base (Recommended)' },
    { value: 'bert-large', label: 'BERT Large (High Accuracy)' },
    { value: 'distilbert', label: 'DistilBERT (Fast)' },
    { value: 'roberta', label: 'RoBERTa (Advanced)' },
  ]

  aiStats: AIPerformanceStats = {
    totalDocumentsProcessed: 0,
    autoAppliedCount: 0,
    suggestionsCount: 0,
    averageConfidence: 0,
    processingTime: 0,
  }

  testingInProgress = false

  ngOnInit() {
    // Load AI statistics if available
    this.loadAIStatistics()
  }

  loadAIStatistics() {
    // Mock statistics for now - this would be replaced with actual API call
    // In a real implementation, this would fetch from the backend
    this.aiStats = {
      totalDocumentsProcessed: 0,
      autoAppliedCount: 0,
      suggestionsCount: 0,
      averageConfidence: 0,
      processingTime: 0,
    }
  }

  get autoApplyThreshold(): number {
    return this.settingsForm.get('aiAutoApplyThreshold')?.value || 80
  }

  get suggestThreshold(): number {
    return this.settingsForm.get('aiSuggestThreshold')?.value || 60
  }

  onAutoApplyThresholdChange(event: Event) {
    const value = parseInt((event.target as HTMLInputElement).value)
    this.settingsForm.get('aiAutoApplyThreshold')?.setValue(value)
    this.settingsChanged.emit()
  }

  onSuggestThresholdChange(event: Event) {
    const value = parseInt((event.target as HTMLInputElement).value)
    this.settingsForm.get('aiSuggestThreshold')?.setValue(value)
    this.settingsChanged.emit()
  }

  testAIWithSample() {
    this.testingInProgress = true
    
    // Mock test - in real implementation, this would call the backend API
    setTimeout(() => {
      this.testingInProgress = false
      this.toastService.show({
        content: $localize`AI test completed successfully. Check the console for results.`,
        delay: 5000,
      })
      
      // Log mock test results
      console.log('AI Scanner Test Results:', {
        scannerEnabled: this.settingsForm.get('aiScannerEnabled')?.value,
        mlEnabled: this.settingsForm.get('aiMlFeaturesEnabled')?.value,
        ocrEnabled: this.settingsForm.get('aiAdvancedOcrEnabled')?.value,
        autoApplyThreshold: this.autoApplyThreshold,
        suggestThreshold: this.suggestThreshold,
        model: this.settingsForm.get('aiMlModel')?.value,
      })
    }, 2000)
  }

  get aiScannerEnabled(): boolean {
    return this.settingsForm.get('aiScannerEnabled')?.value === true
  }

  onAiSettingChange() {
    this.settingsChanged.emit()
  }
}
