import { ObjectWithId } from './object-with-id'

export enum MailFilterAttachmentType {
  Attachments = 1,
  Everything = 2,
}

export enum MailRuleConsumptionScope {
  Attachments = 1,
  Email_Only = 2,
  Everything = 3,
}

export enum MailAction {
  Delete = 1,
  Move = 2,
  MarkRead = 3,
  Flag = 4,
  Tag = 5,
}

export enum MailMetadataTitleOption {
  FromSubject = 1,
  FromFilename = 2,
}

export enum MailMetadataCorrespondentOption {
  FromNothing = 1,
  FromEmail = 2,
  FromName = 3,
  FromCustom = 4,
}

export interface PaperlessMailRule extends ObjectWithId {
  name: string

  account: number // PaperlessMailAccount.id

  order: number

  folder: string

  filter_from: string

  filter_subject: string

  filter_body: string

  filter_attachment_filename: string

  maximum_age: number

  attachment_type: MailFilterAttachmentType

  action: MailAction

  action_parameter?: string

  assign_title_from: MailMetadataTitleOption

  assign_tags?: number[] // PaperlessTag.id

  assign_document_type?: number // PaperlessDocumentType.id

  assign_correspondent_from?: MailMetadataCorrespondentOption

  assign_correspondent?: number // PaperlessCorrespondent.id
}
