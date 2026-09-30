import { AsyncPipe, NgForOf, NgIf } from '@angular/common'
import {
  Component,
  OnInit,
  TemplateRef,
  ViewChild,
  inject,
} from '@angular/core'
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms'
import { NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { AiModel } from 'src/app/data/ai-model'
import { AiModelService } from 'src/app/services/rest/ai-model.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-ai-model-settings',
  templateUrl: './ai-model-settings.component.html',
  styleUrls: ['./ai-model-settings.component.scss'],
  standalone: true,
  imports: [NgForOf, NgIf, AsyncPipe, ReactiveFormsModule],
})
export class AiModelSettingsComponent implements OnInit {
  private aiModelService = inject(AiModelService)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)

  @ViewChild('modelDialog') modelDialogTpl: TemplateRef<any>
  private activeModal?: NgbModalRef

  models: AiModel[] = []
  filteredModels: AiModel[] = []
  loading = false

  /** 当前选中的模型类型过滤器 */
  selectedModelTypeFilter: string = 'ALL'

  /** 可选的模型类型 */
  readonly modelTypeOptions: { value: string; label: string }[] = [
    { value: 'llm', label: $localize`Large language model` },
    { value: 'vlm', label: $localize`Vision-language model` },
    { value: 'asr', label: $localize`Speech recognition (ASR)` },
  ]

  /** 获取所有唯一的模型类型列表（用于过滤标签） */
  get availableModelTypes(): string[] {
    const types = new Set<string>()
    this.models.forEach((model) => {
      if (model.model_type) {
        types.add(model.model_type)
      }
    })
    return Array.from(types).sort()
  }

  selectedModel: AiModel = null

  form = new FormGroup({
    id: new FormControl<number | null>(null),
    name: new FormControl('', [Validators.required]),
    supplier: new FormControl('', [Validators.required]),
    model_type: new FormControl('llm', [Validators.required]),
    base_model: new FormControl('', [Validators.required]),
    api_domain: new FormControl('', [Validators.required]),
    api_key: new FormControl(''),
    is_default: new FormControl(false),
  })

  ngOnInit(): void {
    this.loadModels()
  }

  private openDialog(): void {
    if (!this.modelDialogTpl) {
      return
    }
    this.activeModal = this.modalService.open(this.modelDialogTpl, {
      size: 'xl',
      backdrop: 'static',
    })
  }

  private loadModels(): void {
    this.loading = true
    this.aiModelService.listAllModels().subscribe({
      next: (res) => {
        // 兼容两种格式：直接数组或 Results 格式
        if (Array.isArray(res)) {
          this.models = res
        } else if (res && res.results) {
          this.models = res.results
        } else {
          this.models = []
        }
        this.applyFilter()
        this.loading = false
      },
      error: (err) => {
        this.loading = false
        this.toastService.showError($localize`Error loading AI models`, err)
      },
    })
  }

  /** 应用模型类型过滤器 */
  applyFilter(): void {
    if (this.selectedModelTypeFilter === 'ALL') {
      this.filteredModels = this.models
    } else {
      this.filteredModels = this.models.filter(
        (model) => model.model_type === this.selectedModelTypeFilter
      )
    }
  }

  /** 切换模型类型过滤器 */
  onModelTypeFilterChange(filterType: string): void {
    this.selectedModelTypeFilter = filterType
    this.applyFilter()
  }

  /** 获取模型类型的显示标签 */
  getModelTypeLabel(modelType: string): string {
    const option = this.modelTypeOptions.find((opt) => opt.value === modelType)
    return option ? option.label : modelType
  }

  onCreate(): void {
    this.selectedModel = null
    const isFirstModel =
      Array.isArray(this.models) ? this.models.length === 0 : true
    this.form.reset({
      id: null,
      name: '',
      supplier: '',
      model_type: 'llm',
      base_model: '',
      api_domain: '',
      api_key: '',
      is_default: isFirstModel,
    })
  }

  onCreateClick(): void {
    this.onCreate()
    this.openDialog()
  }

  onEdit(model: AiModel): void {
    this.selectedModel = model
    this.form.reset({
      id: model.id,
      name: model.name,
      supplier: model.supplier,
      model_type: model.model_type || 'llm',
      base_model: model.base_model,
      api_domain: model.api_domain,
      api_key: '',
      is_default: model.is_default,
    })
  }

  onEditClick(model: AiModel): void {
    this.onEdit(model)
    this.openDialog()
  }

  onSetDefault(model: AiModel): void {
    const payload: AiModel = { ...model, is_default: true }
    this.aiModelService.patch(payload).subscribe({
      next: () => {
        this.toastService.showInfo(
          $localize`Default AI model was updated successfully.`
        )
        this.loadModels()
      },
      error: (err) => {
        this.toastService.showError(
          $localize`Error updating default AI model`,
          err
        )
      },
    })
  }

  /** 检查模型是否是当前类型的默认模型 */
  isDefaultForType(model: AiModel): boolean {
    if (!model.is_default) {
      return false
    }
    // 检查是否是该类型中唯一的默认模型
    const sameTypeModels = this.models.filter(
      (m) => m.model_type === model.model_type && m.is_default
    )
    return sameTypeModels.length === 1 && sameTypeModels[0].id === model.id
  }

  onDelete(model: AiModel): void {
    if (!confirm($localize`Are you sure you want to delete this model?`)) {
      return
    }
    this.aiModelService.delete(model).subscribe({
      next: () => {
        this.toastService.showInfo(
          $localize`AI model was deleted successfully.`
        )
        this.loadModels()
        if (this.selectedModel?.id === model.id) {
          this.selectedModel = null
        }
      },
      error: (err) => {
        this.toastService.showError($localize`Error deleting AI model`, err)
      },
    })
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched()
      return
    }
    const raw = this.form.getRawValue()
    const payload: AiModel = {
      id: raw.id,
      name: raw.name,
      supplier: raw.supplier,
      model_type: raw.model_type,
      base_model: raw.base_model,
      api_domain: raw.api_domain,
      api_key: raw.api_key,
      is_default: raw.is_default,
    }

    const request$ = payload.id
      ? this.aiModelService.update(payload)
      : this.aiModelService.create(payload)

    request$.subscribe({
      next: () => {
        this.toastService.showInfo($localize`AI model was saved successfully.`)
        this.loadModels()
        this.selectedModel = null
        if (this.activeModal) {
          this.activeModal.close()
          this.activeModal = null
        }
        // 如果创建了新模型，自动切换到对应的类型过滤器
        if (!payload.id && payload.model_type) {
          this.onModelTypeFilterChange(payload.model_type)
        }
      },
      error: (err) => {
        this.toastService.showError($localize`Error saving AI model`, err)
      },
    })
  }
}
