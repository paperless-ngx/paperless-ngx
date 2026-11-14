const OPERATION_LABELS: Record<string, string> = {
  set_correspondent: $localize`Set correspondent`,
  set_document_type: $localize`Set document type`,
  set_storage_path: $localize`Set storage path`,
  add_tag: $localize`Add tag`,
  remove_tag: $localize`Remove tag`,
  modify_tags: $localize`Update tags`,
  modify_custom_fields: $localize`Update custom fields`,
  set_permissions: $localize`Set permissions`,
  delete: $localize`Move to trash`,
  reprocess: $localize`Document reprocessing`,
  run_workflow: $localize`Run workflow`,
  rotate: $localize`Rotate documents`,
  merge: $localize`Merge documents`,
  merge_as_versions: $localize`Merge as versions`,
  split: $localize`Split documents`,
  delete_pages: $localize`Delete pages`,
  edit_pdf: $localize`Edit PDF`,
  remove_password: $localize`Remove password`,
}

export function getDocumentOperationLabel(operation?: string): string | null {
  const label = operation ? OPERATION_LABELS[operation] : null
  return label ?? null
}
