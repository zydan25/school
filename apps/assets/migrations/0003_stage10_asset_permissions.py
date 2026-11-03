from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_stage10_asset_lifecycle"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="assetdepreciationentry",
            options={
                "verbose_name": "قيد إهلاك أصل",
                "verbose_name_plural": "سجلات إهلاك الأصول",
                "permissions": [
                    ("post_assetdepreciationentry", "Can post asset depreciation entries"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="assetmovement",
            options={
                "verbose_name": "حركة نقل أصل أو عهدة",
                "verbose_name_plural": "سجل نقل الأصول والعهد",
                "permissions": [
                    ("move_assetmovement", "Can move assets and change custody"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="assetdisposal",
            options={
                "verbose_name": "مستند استبعاد أصل",
                "verbose_name_plural": "مستندات استبعاد الأصول",
                "permissions": [
                    ("dispose_assetdisposal", "Can dispose fixed assets"),
                ],
            },
        ),
    ]
