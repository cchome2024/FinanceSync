import { useRouter } from 'expo-router'
import { StyleProp, Text, TextStyle, TouchableOpacity } from 'react-native'

type NavLinkProps = {
  href: string
  label: string
  textStyle?: StyleProp<TextStyle>
}

export function NavLink({ href, label, textStyle }: NavLinkProps) {
  const router = useRouter()

  const handlePress = () => {
    router.push(href)
  }

  return (
    <TouchableOpacity onPress={handlePress} activeOpacity={0.8}>
      <Text style={textStyle}>{label}</Text>
    </TouchableOpacity>
  )
}
