from documents.loggers import LoggingMixin
from documents.models import CustomFieldInstance, Document, Dossier
from paperless.models import ApplicationConfiguration


class UpdateDataDocument(LoggingMixin):
    def fill_custom_field_default(self,document:Document, data_ocr_fields):
        fields = CustomFieldInstance.objects.filter(
                                    document=document,
                                )
        dict_data = {}
        try:
            if data_ocr_fields is not None:
                if isinstance(data_ocr_fields[0],list):

                    for r in data_ocr_fields[0][0].get("fields"):
                        dict_data[r.get("name")] = r.get("values")[0].get("value") if r.get("values") else None
                    user_args=ApplicationConfiguration.objects.filter().first().user_args
                    mapping_field_user_args = []
                    for f in user_args.get("form_code",[]):
                        if f.get("name") == data_ocr_fields[1]:
                            mapping_field_user_args = f.get("mapping",[])
                    map_fields = {}
                    for key,value in mapping_field_user_args[0].items():
                        map_fields[key]=dict_data.get(value)
                    for f in fields:
                        f.value_text = map_fields.get(f.field.name,None)
                    CustomFieldInstance.objects.bulk_update(fields, ['value_text'])
        except Exception as e:
            self.log.error("error ocr field",e)

    def fill_custom_field(self,document:Document, data_ocr_fields, dossier_file:Dossier):
        dict_data = {}
        if data_ocr_fields is not None and isinstance(data_ocr_fields[0], list) == True:
            if len(data_ocr_fields[0])>=1:
                for r in data_ocr_fields[0][0].get("fields"):

                    dict_data[r.get("name")] = r.get("values")[0].get("value") if r.get("values") else None
                custom_fields = CustomFieldInstance.objects.filter(dossier=document.dossier)
                document_dossier_form = self.get_config_dossier_form()
                custom_fields_form = CustomFieldInstance.objects.filter(dossier_form=document_dossier_form)
                # map custom_fields to dict for search
                dict_custom_fields = {}
                for f in custom_fields:
                    dict_custom_fields[f.field] = f
                if(custom_fields_form):
                    for r in custom_fields_form:
                        r: CustomFieldInstance

                        if dict_custom_fields.get(r.field) is not None:
                            dict_custom_fields[r.field].value_text=dict_data.get(r.match_value)
                        # self.log.info('gia tri field',r.field)
                        # r.value_text = dict_data.get(r.match_value)
                        # self.log.debug("gia tri value map",r.match_value)
                        # create dossier file
                        CustomFieldInstance.objects.update_or_create(field=r.field,
                                                                     document=document,
                                                                     defaults={"value_text":dict_data.get(r.match_value),"dossier":dossier_file})

                #     for r in custom_fields:
                #         r: CustomFieldInstance

                #         r.value_text = dict_data.get(r.match_value)
                #         # self.log.debug("gia tri value map",r.match_value)
                #         # create dossier file
                #         # CustomFieldInstance.objects.create(field=r.field,
                #         #                                    value_text=dict_data.get(r.match_value),
                #         #                                    dossier = dossier_file,
                #         #                                    document=document)

                CustomFieldInstance.objects.bulk_update(custom_fields, ['value_text'])
                # assign new value to dossier by dossier_form----------------

                # get custom field be assign
                query_custom_fields_dossier_document_form = CustomFieldInstance.objects.filter(dossier_form=document_dossier_form, reference__isnull=True)
                dict_custom_fields_dossier_document_form = {obj.field.id: obj for obj in query_custom_fields_dossier_document_form}
                query_custom_fields_dossier_document = CustomFieldInstance.objects.filter(dossier=document.dossier,reference__isnull=True)
                dict_custom_fields_dossier_document = {obj.field.id: obj for obj in query_custom_fields_dossier_document}
                dict_custom_fields_document_reference = {}
                for field, obj in dict_custom_fields_dossier_document_form.items():
                    if dict_custom_fields_dossier_document.get(field) is not None:

                        dict_custom_fields_document_reference[obj.id]=dict_custom_fields_dossier_document.get(field)

                # get dossier_form by document_form
                lst_id_dossier = dossier_file.path.split("/")
                lst_id_dossier = [int(num) for num in lst_id_dossier]
                lst_dossiers = Dossier.objects.filter(id__in=lst_id_dossier,type="DOSSIER")
                # dossier_forms = custom_fields = CustomFieldInstance.objects.filter(dossier_form=document_dossier_form)
                for d in lst_dossiers:
                    query_custom_fields_dossier_form = CustomFieldInstance.objects.filter(dossier_form=d.dossier_form,reference__isnull=False)
                    dict_custom_fields_dossier_form = {obj.field.id: obj for obj in query_custom_fields_dossier_form}
                    query_custom_fields_dossier = CustomFieldInstance.objects.filter(dossier=d,reference__isnull=True)
                    dict_custom_fields_dossier = {obj.field.id: obj for obj in query_custom_fields_dossier}
                    dict_custom_fields_dossier_reference = {}
                    for field, obj in dict_custom_fields_dossier_form.items():
                        if dict_custom_fields_dossier.get(field) is not None:
                            dict_custom_fields_dossier_reference[obj.reference.id]=dict_custom_fields_dossier.get(field)
                        elif dict_custom_fields_dossier.get(field) is None:
                            CustomFieldInstance.objects.create(field=obj.field,
                                                           value_text='',
                                                           dossier = d,
                                                        )
                    for field, obj in dict_custom_fields_dossier_reference.items():
                        if dict_custom_fields_document_reference.get(field) is not None:
                            obj:CustomFieldInstance
                            obj.value_text=dict_custom_fields_document_reference.get(field).value_text
                    CustomFieldInstance.objects.bulk_update(dict_custom_fields_dossier_reference.values(), ['value_text'])
